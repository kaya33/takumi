# -*- coding: utf-8 -*-

import mock


def test_context(mock_config):
    from takumi_service.service import Context
    ctx = Context()
    ctx.hello = 90
    ctx.world = 'hello'
    ctx.yes = 'no'
    assert ctx == {'yes': 'no', 'hello': 90, 'world': 'hello'}
    ctx.clear_except('hello', 'yes')
    assert ctx == {'hello': 90, 'yes': 'no'}


def test_service(mock_config):
    from takumi_service.service import TakumiService, ServiceHandler
    handler = ServiceHandler('TestService')

    @handler.api
    def ping():
        return 'pong'

    mock_config.thrift_file = 'tests/test.thrift'
    service = TakumiService()
    service.set_handler(handler)
    m = service.api_map._ApiMap__map
    assert 'ping' in m
    assert m['ping'].func is ping
    assert m['ping'].conf == {'hard_timeout': 20, 'soft_timeout': 3}
    assert getattr(handler.thrift_module, 'TestService') is service.service_def


def test_api_map(mock_config):
    from takumi_service.service import ApiMap, Context, ServiceHandler

    handler = ServiceHandler('TestService')

    @handler.api
    def ping():
        return 'pong'

    api_map = ApiMap(handler, Context(client_addr='127.0.0.1'))
    assert api_map.ping().value == 'pong'


def test_handler(mock_config):
    from takumi_service.service import _Handler

    def ping():
        return 'pong'

    handler = _Handler(ping, {'soft_timeout': 30, 'hard_timeout': 50})
    assert handler() == 'pong'


def test_service_handler(mock_config):
    from takumi_service.service import ServiceHandler

    handler = ServiceHandler('TestService', soft_timeout=10, hard_timeout=30)

    @handler.api
    def ping():
        return 'pong'

    @handler.api(soft_timeout=15)
    def ping2():
        return 'pong2'

    assert handler.api_map['ping'].func is ping
    assert handler.api_map['ping'].conf['soft_timeout'] == 10
    assert handler.api_map['ping2'].func is ping2
    assert handler.api_map['ping2'].conf['soft_timeout'] == 15
    assert handler.service_name == 'TestService'


def test_extend(mock_config):
    from takumi_service.service import ServiceHandler, ServiceModule

    app = ServiceHandler('TestService')
    mod = ServiceModule()

    @mod.api
    def ping():
        return 'pong'

    app.extend(mod)
    assert app.api_map['ping'].func is ping


def test_use_hook(mock_config):
    from takumi_service.service import ServiceHandler
    from takumi_service.hook import define_hook
    app = ServiceHandler('TestService')

    @define_hook(event='test_hook')
    def test_hook():
        return 'hello world'

    app.use(test_hook)
    assert app.hook_registry.on_test_hook() == ['hello world']


def test_with_ctx(mock_config):
    from takumi_service.service import ApiMap
    handler = mock.Mock()
    handler.conf = {'soft_timeout': 1, 'hard_timeout': 5, 'with_ctx': True}
    m = mock.Mock(api_map={'ping': handler})
    api_map = ApiMap(m, {'client_addr': 'localhost', 'meta': {'hello': '123'}})
    api_map.ping(1, 2, 'hello', [])
    handler.assert_called_with(
        {'meta': {'hello': '123'}, 'client_addr': 'localhost'},
        1, 2, 'hello', [])

    handler.conf.pop('with_ctx')
    api_map.ping(1, 2, 'hello', [])
    handler.assert_called_with(1, 2, 'hello', [])


def test_exceptions(mock_config, monkeypatch):
    import socket
    from takumi_service.service import TakumiService, Processor, \
        CloseConnectionError, TakumiBinaryProtocol
    from thriftpy.transport import TTransportException, TSocket
    from thriftpy.protocol.exc import TProtocolException
    service = TakumiService()
    service.api_map = {}
    service.context.update(
        {'client_addr': 'localhost', 'client_port': 1, })

    t_exc = TTransportException()
    t_exc.message = 'end of file'
    sock = TSocket()
    sock.sock = socket.socket()

    mock_close = mock.Mock()
    monkeypatch.setattr(TakumiBinaryProtocol, 'close', mock_close)

    t_exc.type = TTransportException.END_OF_FILE
    with mock.patch.object(Processor, 'process', side_effect=t_exc):
        service.run(sock)

    service.logger = mock.Mock(exception=mock.Mock())
    t_exc.type = TTransportException.ALREADY_OPEN
    with mock.patch.object(Processor, 'process', side_effect=t_exc):
        service.run(sock)
    service.logger.exception.assert_called_with(t_exc)

    p_exc = TProtocolException()
    p_exc.type = TProtocolException.BAD_VERSION
    with mock.patch.object(Processor, 'process', side_effect=p_exc):
        service.run(sock)
    service.logger.warn.assert_called_with(
        '[%s:%s] protocol error: %s', 'localhost', 1, p_exc)

    c_exc = CloseConnectionError()
    with mock.patch.object(Processor, 'process', side_effect=c_exc):
        service.run(sock)

    mock_close.assert_called_with()
