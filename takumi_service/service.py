# -*- coding: utf-8 -*-

"""
takumi_service.service
~~~~~~~~~~~~~~~~~~~~~~

This module implements service runner and handler definition interface.

Available hooks:

    - before_api_call  Hooks to be executed before api called.
    - api_called       Hooks to be executed after api called.
    - api_timeout      Hooks to be executed after api call timeout.

Registered hooks:

    - api_called
"""

import contextlib
import functools
import gevent
import logging
import os.path
import sys
import time
from copy import deepcopy

from thriftpy import load
from thriftpy.thrift import TProcessorFactory, TProcessor, TException
from thriftpy.transport import TBufferedTransportFactory
from thriftpy.protocol import TBinaryProtocolFactory

from takumi_config import config

from .hook import hook_registry
from .hook.api import api_called
from ._compat import reraise

# register api hook
hook_registry.register(api_called)


@contextlib.contextmanager
def _ignore_exception(logger):
    try:
        yield
    except Exception as e:
        logger.exception(e)


class Context(dict):
    """Runtime context.

    This class is used to track runtime informations.
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

    def clear_except(self, *keys):
        """Clear the dict except the given key.

        :param keys: not delete the values of these keys
        """
        reserved = [(k, self.get(k)) for k in keys]
        self.clear()
        self.update(reserved)


class TakumiService(object):
    """Takumi service runner.

    :Example:

    >>> service = TakumiService()
    >>> service.context.update({'client_addr': '0.0.0.0:1234'})
    >>> servcie.set_handler(handler)
    >>> service.run()
    """
    def __init__(self):
        self.context = Context()
        self.handler = None
        self.service_def = None

    def set_handler(self, handler):
        """Fill the service handler for this service.

        :param handler: a :class:`ServiceHandler` instance
        """

        self.api_map = ApiMap(handler, self.context)
        self.service_def = getattr(handler.thrift_module, handler.service_name)

    def run(self, sock):
        """The main run loop for the service.

        :param sock: the client socket
        """

        processor = TProcessorFactory(
            TProcessor,
            self.service_def,
            self.api_map
        ).get_processor()

        itrans = TBufferedTransportFactory().get_transport(sock)
        iproto = TBinaryProtocolFactory().get_protocol(itrans)
        otrans = TBufferedTransportFactory().get_transport(sock)
        oproto = TBinaryProtocolFactory().get_protocol(otrans)

        try:
            while True:
                processor.process(iproto, oproto)
        finally:
            itrans.close()
            otrans.close()


class ApiMap(object):
    """Record service handlers.

    :param handler: a :class:`ServiceHandler` instance
    :param env: environment context for this api map
    """
    def __init__(self, handler, env):
        self.__map = handler.api_map
        self.__ctx = Context()
        self.__ctx.env = env
        self.__system_exc_handler = handler.system_exc_handler
        self.__api_exc_handler = handler.api_exc_handler
        self.__thrift_exc_handler = handler.thrift_exc_handler

    def __setitem__(self, attr, item):
        self.__map[attr] = item

    def __call(self, api_name, handler, *args, **kwargs):
        ctx = self.__ctx

        # Clear context except env
        ctx.clear_except('env')
        ctx.update({
            'args': args,
            'kwargs': kwargs,
            'api_name': api_name,
            'start_at': time.time(),
            'logger': logging.getLogger(handler.__module__)
        })
        ctx.soft_timeout = handler.conf['soft_timeout']
        ctx.hard_timeout = handler.conf['hard_timeout']

        if ctx.hard_timeout < ctx.soft_timeout:
            ctx.logger.warning(
                'Api soft timeout {!r}s greater than hard timeout {!r}s'
                .format(ctx.soft_timeout, ctx.hard_timeout))

        ctx.exc = None

        # Before api call hook
        try:
            hook_registry.on_before_api_call(ctx)
        except Exception:
            reraise(*self.__system_exc_handler(*sys.exc_info()))

        try:
            with gevent.Timeout(ctx.hard_timeout):
                ret = handler(*args, **kwargs)
                ctx.return_value = ret
                return ret
        except TException as e:
            ctx.exc = e
            reraise(*self.__thrift_exc_handler(*sys.exc_info()))
        except gevent.Timeout as e:
            ctx.exc = e
            with _ignore_exception(ctx.logger):
                hook_registry.on_api_timeout(ctx)
            reraise(*self.__system_exc_handler(*sys.exc_info()))
        except Exception as e:
            ctx.exc = e
            reraise(*self.__api_exc_handler(*sys.exc_info()))
        finally:
            ctx.end_at = time.time()
            # After api call hook
            with _ignore_exception(ctx.logger):
                hook_registry.on_api_called(ctx)

    def __getattr__(self, api_name):
        if api_name not in self.__map:
            raise AttributeError('{!r} object has no attribute {!r}'.format(
                self.__class__.__name__, api_name))
        return functools.partial(self.__call, api_name, self.__map[api_name])


class _Handler(object):
    """Api handler.

    Every api is wrapped with this class for configuration. Every api can be
    configured.
    """
    def __init__(self, func, conf):
        """Create a new Handler instance.

        :param func: api function
        :param conf: api configuration dict
        """
        functools.wraps(func)(self)
        self.func = func
        self.conf = conf

    def __call__(self, *args, **kwargs):
        """Delegate to the true function.
        """
        return self.func(*args, **kwargs)


class ServiceModule(object):
    """This class makes it convinent to implement api in different modules.
    """
    def __init__(self, **kwargs):
        self.conf = kwargs
        self.api_map = {}

    def add_api(self, name, func, conf):
        """Add an api

        :param name: api name
        :param func: function implement the api
        :param conf: api configuration
        """
        self.api_map[name] = _Handler(func, conf)

    def api(self, name=None, **conf):
        """Used to register a handler func.

        :param name: alternative api name, the default name is function name
        """
        api_conf = deepcopy(self.conf)
        api_conf.update(conf)

        # Direct decoration
        if callable(name):
            self.add_api(name.__name__, name, api_conf)
            return name

        def deco(func):
            api_name = name or func.__name__
            self.add_api(api_name, func, api_conf)
            return func
        return deco


class ServiceHandler(ServiceModule):
    """Takumi service handler.

    This class is used to define a Takumi app. It will load thrift module and
    set ``thrift_module`` for thrift module attribute access.

    :Example:

    app = ServiceHandler('PingService')

    @app.api()
    def ping():
        return 'pong'
    """
    def __init__(self, service_name, soft_timeout=3, hard_timeout=20,
                 **kwargs):
        self.service_name = service_name
        super(ServiceHandler, self).__init__(
            soft_timeout=soft_timeout, hard_timeout=hard_timeout, **kwargs)
        self.system_exc_handler = self._default_exception_handler
        self.api_exc_handler = self._default_exception_handler
        self.thrift_exc_handler = self._default_exception_handler

        module_name, _ = os.path.splitext(os.path.basename(config.thrift_file))
        # module name should ends with '_thrift'
        if not module_name.endswith('_thrift'):
            module_name = ''.join([module_name, '_thrift'])
        self.thrift_module = load(config.thrift_file, module_name=module_name)

    @staticmethod
    def _default_exception_handler(tp, val, tb):
        return tp, val, tb

    def extend(self, module):
        """Extend app with another service module

        :param module: instance of :class:`ServiceModule`
        """
        for api_name, handler in module.api_map.items():
            api_conf = deepcopy(self.conf)
            api_conf.update(handler.conf)
            self.add_api(api_name, handler.func, api_conf)

    @staticmethod
    def use(hook):
        """Apply hook for this app

        :param hook: a :class:`takumi_service.hook.Hook` instance
        """
        hook_registry.register(hook)

    def handle_system_exception(self, func):
        """Set system exception handler

        :param func: the function to handle system exceptions
        """
        self.system_exc_handler = func
        return func

    def handle_api_exception(self, func):
        """Set application exception handler

        :Example:

        .. code-block:: python

            @app.handle_api_exception
            def app_exception(tp, value, tb):
                exc = app_thrift.UnknownException()
                exc.value = value
                exc.with_traceback(tb)
                return exc.__class__, exc, tb

        :param func: the function to handle application exceptions
        """
        self.api_exc_handler = func
        return func

    def handle_thrift_exception(self, func):
        """Set thrift exception handler

        :param func: the function to handle thrift exceptions
        """
        self.thrift_exc_handler = func
        return func

    def __call__(self):
        """Make it callable
        """
