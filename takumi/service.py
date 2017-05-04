# -*- coding: utf-8 -*-

"""
takumi.service
~~~~~~~~~~~~~~

This module implements service runner and handler definition interface.

Available hooks:

    - before_api_call  Hooks to be executed before api called.
    - api_called       Hooks to be executed after api called.
    - api_timeout      Hooks to be executed after api call timeout.

Registered hooks:

    - api_called
    - config_log
"""

import contextlib
import functools
import gevent
import itertools
import logging
import os.path
import sys
import time
from copy import deepcopy

from thriftpy import load
from thriftpy.thrift import TProcessorFactory, TException, \
    TApplicationException
from thriftpy.transport import TBufferedTransport, TTransportException
from thriftpy.protocol import TBinaryProtocol

from takumi_config import config
from takumi_thrift import Processor, Response

from .exc import CloseConnectionError, TimeoutException
from .hook import HookRegistry, StopHook
from .hook.api import api_called
from ._compat import reraise, protocol_exceptions
from .log import MetaAdapter, config_log


SOFT_TIMEOUT = 3
HARD_TIMEOUT = 20


@contextlib.contextmanager
def _ignore_hook_exception(logger):
    try:
        yield
    except Exception as e:
        logger.warning('Ignore hook function exception: %s', e, exc_info=True)


class Context(dict):
    """Runtime context.

    This class is used to track runtime informations.
    """
    __setattr__ = dict.__setitem__

    def __getattr__(self, attr):
        if attr not in self:
            raise AttributeError(
                'Context object has no attribute {!r}'.format(attr))
        return self[attr]

    def clear_except(self, *keys):
        """Clear the dict except the given key.

        :param keys: not delete the values of these keys
        """
        reserved = [(k, self.get(k)) for k in keys]
        self.clear()
        self.update(reserved)


class TakumiBinaryProtocol(object):
    """Thrift binary protocol wrapper

    Used for ``thrift_protocol_class`` config.

    :param sock: client socket
    """
    def __init__(self, sock):
        self.sock = sock
        self.trans = None

    def get_proto(self):
        """Create a TBinaryProtocol instance
        """
        self.trans = TBufferedTransport(self.sock)
        return TBinaryProtocol(self.trans)

    def close(self):
        """Close underlying transport
        """
        if self.trans is not None:
            try:
                self.trans.close()
            finally:
                self.trans = None


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
        self.logger = logging.getLogger('takumi')

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
            Processor,
            self.context,
            self.service_def,
            self.api_map
        ).get_processor()

        proto_class = config.thrift_protocol_class or TakumiBinaryProtocol
        factory = proto_class(sock)
        proto = factory.get_proto()
        try:
            while True:
                processor.process(proto, proto)
        except TTransportException as e:
            # Ignore EOF exception
            if e.type != TTransportException.END_OF_FILE:
                self.logger.exception(e)
        except protocol_exceptions as e:
            self.logger.warn(
                '[%s:%s] protocol error: %s',
                self.context['client_addr'], self.context['client_port'], e)
        except CloseConnectionError:
            pass
        finally:
            factory.close()


class ApiMap(object):
    """Record service handlers.

    :param handler: a :class:`ServiceHandler` instance
    :param env: environment context for this api map
    """
    def __init__(self, handler, env):
        self.__map = handler.api_map
        self.__ctx = Context()
        # Set response meta
        env.response_meta = {}
        self.__ctx.env = env
        self.__hook = handler.hook_registry
        self.__system_exc_handler = handler.system_exc_handler
        self.__api_exc_handler = handler.api_exc_handler
        self.__thrift_exc_handler = handler.thrift_exc_handler

    def __setitem__(self, attr, item):
        self.__map[attr] = item

    def __call(self, api_name, handler, *args, **kwargs):
        ctx = self.__ctx
        # Clear response meta
        ctx.env['response_meta'].clear()
        # Add utility attributes to ctx
        ctx.update(args=args, kwargs=kwargs, api_name=api_name,
                   start_at=time.time(), conf=handler.conf,
                   meta=ctx.env['meta'],
                   response_meta=ctx.env['response_meta'])
        ctx.logger = MetaAdapter(
            logging.getLogger(handler.__module__), {'ctx': ctx})

        ctx.conf.setdefault('soft_timeout', SOFT_TIMEOUT)
        ctx.conf.setdefault('hard_timeout', HARD_TIMEOUT)

        soft_timeout = ctx.conf['soft_timeout']
        hard_timeout = ctx.conf['hard_timeout']
        with_ctx = ctx.conf.get('with_ctx', False)

        if hard_timeout < soft_timeout:
            ctx.logger.warning(
                'Api soft timeout {!r}s greater than hard timeout {!r}s'
                .format(soft_timeout, hard_timeout))

        ctx.exc = None

        try:
            # Before api call hook
            try:
                self.__hook.on_before_api_call(ctx)
            except StopHook as e:
                ret = Response(value=e.value, meta=e.meta)
                ctx.return_value = ret
                return ret
            except Exception as e:
                ctx.exc = e
                reraise(*self.__system_exc_handler(*sys.exc_info()))

            try:
                args = itertools.chain([ctx], args) if with_ctx else args
                with gevent.Timeout(hard_timeout,
                                    exception=TimeoutException(hard_timeout)):
                    ret = handler(*args, **kwargs)
                    if not isinstance(ret, Response):
                        ret = Response(ret)
                    ctx.return_value = ret
                    return ret
            except TException as e:
                ctx.exc = e
                reraise(*self.__thrift_exc_handler(*sys.exc_info()))
            except TimeoutException as e:
                ctx.exc = e
                with _ignore_hook_exception(ctx.logger):
                    self.__hook.on_api_timeout(ctx)
                reraise(*self.__system_exc_handler(*sys.exc_info()))
            except Exception as e:
                ctx.exc = e
                reraise(*self.__api_exc_handler(*sys.exc_info()))
        finally:
            ctx.end_at = time.time()
            # After api call hook
            with _ignore_hook_exception(ctx.logger):
                self.__hook.on_api_called(ctx)
            # Clear context
            ctx.clear_except('env')

    def __getattr__(self, api_name):
        func = self.__map.get(api_name, _Handler.undefined(api_name))
        return functools.partial(self.__call, api_name, func)


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

    @classmethod
    def undefined(cls, api_name):
        """Generate an undefined api handler
        """
        def temp_func(*args, **kwargs):
            raise TApplicationException(
                TApplicationException.UNKNOWN_METHOD,
                message='API {!r} undefined'.format(api_name))
        return cls(temp_func, {})


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

    def api_with_ctx(self, *args, **kwargs):
        """Same as api except that the first argument of the func will
        be api environment
        """
        kwargs['with_ctx'] = True
        return self.api(*args, **kwargs)


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
    def __init__(self, service_name, **kwargs):
        self.service_name = service_name
        super(ServiceHandler, self).__init__(**kwargs)

        self.system_exc_handler = self.default_exception_handler
        self.api_exc_handler = self.default_exception_handler
        self.thrift_exc_handler = lambda tp, v, tb: (tp, v, tb)

        # init hook registry
        self.hook_registry = HookRegistry()
        # register api hook
        self.hook_registry.register(api_called)
        # register log config hook
        self.hook_registry.register(config_log)

        module_name, _ = os.path.splitext(os.path.basename(config.thrift_file))
        # module name should ends with '_thrift'
        if not module_name.endswith('_thrift'):
            module_name = ''.join([module_name, '_thrift'])
        self.thrift_module = load(config.thrift_file, module_name=module_name)

    @staticmethod
    def default_exception_handler(tp, val, tb):
        e = TApplicationException(TApplicationException.INTERNAL_ERROR,
                                  message=str(val))
        return TApplicationException, e, tb

    def extend(self, module):
        """Extend app with another service module

        :param module: instance of :class:`ServiceModule`
        """
        for api_name, handler in module.api_map.items():
            api_conf = deepcopy(self.conf)
            api_conf.update(handler.conf)
            self.add_api(api_name, handler.func, api_conf)

    def use(self, hook):
        """Apply hook for this app

        :param hook: a :class:`takumi_service.hook.Hook` instance
        """
        self.hook_registry.register(hook)

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
