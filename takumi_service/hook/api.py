# -*- coding: utf-8 -*-

"""
takumi_service.hook.api
~~~~~~~~~~~~~~~~~~~~~~~

Implement api related hooks.
"""

import gevent
from itertools import starmap, chain
from . import define_hook


def _args(args, kwargs):
    spec = chain(map(repr, args), starmap('{}={!r}'.format, kwargs.items()))
    return ','.join(spec)


@define_hook(event='api_called')
def api_called(ctx):
    logger = ctx.logger
    cost = (ctx.end_at - ctx.start_at) * 1000
    args = _args(ctx.args, ctx.kwargs)

    exc = ctx.exc

    meta = '[{}]'.format(ctx.env.client_addr)
    func_info = '{}({}) {:.6}ms'.format(ctx.api_name, args, cost)

    def with_meta(msg):
        data = [meta, func_info]
        if msg:
            data.insert(1, msg)
        return ' '.join(data)

    # Success
    if not exc:
        if cost > ctx.soft_timeout:
            logger.warn(with_meta('Soft timeout!'))
        elif ctx.api_name != 'ping':
            logger.info(with_meta(''))
    # Gevent timeout
    elif isinstance(exc, gevent.Timeout):
        logger.exception(with_meta('Gevent timeout!'))
    # Exceptions
    else:
        logger.exception(with_meta('{} =>'.format(exc)))
