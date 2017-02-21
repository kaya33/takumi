# -*- coding: utf-8 -*-


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
    assert getattr(service.thrift_module, 'TestService') is service.service_def


def test_api_map(mock_config):
    from takumi_service.service import ApiMap, Context

    def ping():
        return 'pong'
    ping.conf = {'soft_timeout': 30, 'hard_timeout': 50}

    api_map = ApiMap({'ping': ping}, Context(client_addr='127.0.0.1'))
    assert api_map.ping() == 'pong'


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
