# -*- coding: utf-8 -*-

import pytest
import sys

from thriftpy.thrift import TApplicationException


def test_exception_decorator():
    from takumi.service import ServiceHandler

    try:
        raise TypeError('type error')
    except Exception:
        exc_info = sys.exc_info()

    app = ServiceHandler('TestService')

    for t, e, tb in [
            app.system_exc_handler(*exc_info),
            app.api_exc_handler(*exc_info),
    ]:
        assert tb == exc_info[2]
        assert t is TApplicationException
        assert isinstance(e, TApplicationException)
        assert e.type == 6
        assert e.message == 'type error'

    t, e, tb = app.thrift_exc_handler(*exc_info)
    assert tb == exc_info[2]
    assert t is TypeError
    assert isinstance(e, TypeError)

    try:
        raise AttributeError
    except Exception:
        info = sys.exc_info()

    @app.handle_system_exception
    def system_exception(tp, value, tb):
        return info

    @app.handle_api_exception
    def api_exception(tp, value, tb):
        return info

    @app.handle_thrift_exception
    def thrift_exception(tp, value, tb):
        return info

    assert app.system_exc_handler(*exc_info) == info
    assert app.api_exc_handler(*exc_info) == info
    assert app.thrift_exc_handler(*exc_info) == info


def test_before_api_call_raise_exception():
    from takumi.service import ServiceHandler, ApiMap, Context
    from takumi.hook import define_hook

    try:
        raise TypeError('type error')
    except Exception:
        info = sys.exc_info()

    app = ServiceHandler('TestService')

    @app.handle_system_exception
    def system_exception(tp, value, tb):
        return info[0], info[1], tb

    @define_hook(event='before_api_call')
    def raise_a_exception(ctx):
        raise AttributeError('exc')
    app.use(raise_a_exception)

    @app.api
    def raise_test():
        return 'should not be called'

    api_map = ApiMap(app, Context({'client_addr': 'localhost', 'meta': {}}))
    with pytest.raises(TypeError) as exc:
        api_map.raise_test()
    assert str(exc.value) == 'type error'


def test_api_exception():
    from takumi.service import ServiceHandler, ApiMap, Context

    app = ServiceHandler('TestService')

    class ApiException(Exception):
        def __init__(self, exc):
            self.exc = exc

    @app.handle_api_exception
    def api_exception(tp, value, tb):
        exc = ApiException(value)
        return ApiException, exc, tb

    @app.api
    def api_unknown_raise():
        raise TypeError('type error')

    api_map = ApiMap(app, Context({'client_addr': 'localhost', 'meta': {}}))
    with pytest.raises(ApiException) as exc:
        api_map.api_unknown_raise()
    assert isinstance(exc.value, ApiException)
    assert isinstance(exc.value.exc, TypeError)
    assert str(exc.value.exc) == 'type error'


def test_thrift_exception():
    from takumi.service import ServiceHandler, ApiMap, Context
    from thriftpy.thrift import TException

    class ThriftException(TException):
        def __init__(self, msg):
            self.msg = msg

        def __repr__(self):
            return self.msg

    app = ServiceHandler('TestService')

    @app.handle_thrift_exception
    def thrift_exception(tp, value, tb):
        exc = TypeError(str(value))
        return TypeError, exc, tb

    @app.api
    def thrift_raise():
        raise ThriftException('thrift raise')

    api_map = ApiMap(app, Context({'client_addr': 'localhost', 'meta': {}}))
    with pytest.raises(TypeError) as exc:
        api_map.thrift_raise()
    assert str(exc.value) == 'thrift raise'


def test_timeout():
    from takumi.service import ServiceHandler, ApiMap, Context
    import gevent
    app = ServiceHandler('TestService', soft_timeout=0, hard_timeout=1)

    class UnknownException(Exception):
        def __init__(self, exc):
            self.exc = exc

    @app.handle_system_exception
    def system_exception(tp, value, tb):
        exc = UnknownException(value)
        return UnknownException, exc, tb

    @app.api
    def timeout():
        gevent.sleep(2)

    api_map = ApiMap(app, Context({'client_addr': 'localhost', 'meta': {}}))
    with pytest.raises(UnknownException) as exc:
        api_map.timeout()
    assert str(exc.value.exc) == 'Timeout after 1 seconds'
