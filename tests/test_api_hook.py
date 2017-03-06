# -*- coding: utf-8 -*-

import mock
import gevent


def test_api_called():
    ctx = type('_ctx', (object,), {})
    ctx.conf = {}
    ctx.logger = mock.Mock()
    ctx.end_at = 10
    ctx.start_at = 5
    ctx.args = (4, 'hello')
    ctx.kwargs = {'name': 'sarah'}
    ctx.api_name = 'ping_api'

    from takumi.hook.api import api_called
    ctx.exc = None
    ctx.conf['soft_timeout'] = 3000
    api_called(ctx)
    ctx.logger.warn.assert_called_with(
        "Soft timeout! ping_api(4,'hello',name='sarah') 5000.0ms")
    ctx.conf['soft_timeout'] = 6000
    api_called(ctx)
    ctx.logger.info.assert_called_with(
        "ping_api(4,'hello',name='sarah') 5000.0ms")
    ctx.exc = gevent.Timeout(20)
    api_called(ctx)
    ctx.logger.exception.assert_called_with(
        "Gevent timeout! ping_api(4,'hello',name='sarah') 5000.0ms")
    ctx.exc = TypeError('other error')
    api_called(ctx)
    ctx.logger.exception.assert_called_with(
        "other error => ping_api(4,'hello',name='sarah') 5000.0ms")
