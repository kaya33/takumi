# -*- coding: utf-8 -*-

import mock
import gevent


def mock_register(event):
    def deco(func):
        return func
    return deco


def test_api_called():
    import takumi_service.hook as hook

    ctx = type('_ctx', (object,), {})
    ctx.logger = mock.Mock()
    ctx.end_at = 10
    ctx.start_at = 5
    ctx.args = (4, 'hello')
    ctx.kwargs = {'name': 'sarah'}
    ctx.env = type('_env', (object,), {})
    ctx.env.client_addr = '127.0.0.1'
    ctx.api_name = 'ping_api'

    with mock.patch.object(hook, 'register_hook', mock_register):
        from takumi_service.hook.api import api_called
        ctx.exc = None
        ctx.soft_timeout = 3000
        api_called(ctx)
        ctx.logger.warn.assert_called_with(
            "[127.0.0.1] Soft timeout! "
            "ping_api(4,'hello',name='sarah') 5000ms")
        ctx.soft_timeout = 6000
        api_called(ctx)
        ctx.logger.info.assert_called_with(
            "[127.0.0.1] ping_api(4,'hello',name='sarah') 5000ms")
        ctx.exc = gevent.Timeout(20)
        api_called(ctx)
        ctx.logger.exception.assert_called_with(
            "[127.0.0.1] Gevent timeout! "
            "ping_api(4,'hello',name='sarah') 5000ms")
        ctx.exc = TypeError('other error')
        api_called(ctx)
        ctx.logger.exception.assert_called_with(
            "[127.0.0.1] other error => "
            "ping_api(4,'hello',name='sarah') 5000ms")
