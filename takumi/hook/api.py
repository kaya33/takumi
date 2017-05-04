# -*- coding: utf-8 -*-

"""
takumi.hook.api
~~~~~~~~~~~~~~~

Implement api related hooks.
"""

from itertools import starmap, chain
from . import define_hook
from ..exc import TimeoutException


def _args(args, kwargs):
    spec = chain(map(repr, args), starmap('{}={!r}'.format, kwargs.items()))
    return ','.join(spec)


@define_hook(event='api_called')
def api_called(ctx):
    logger = ctx.logger
    cost = (ctx.end_at - ctx.start_at) * 1000
    args = _args(ctx.args, ctx.kwargs)
    func_info = '{}({}) {:.6}ms'.format(ctx.api_name, args, float(cost))

    def _func_info(msg=None):
        if not msg:
            return func_info
        return ' '.join([msg, func_info])

    exc = ctx.exc
    # Success
    if not exc:
        if cost > ctx.conf['soft_timeout']:
            logger.warn(_func_info('Soft timeout!'))
        elif ctx.api_name != 'ping':
            logger.info(_func_info())
    # Timeout
    elif isinstance(exc, TimeoutException):
        logger.exception(_func_info('Timeout!'))
    # Exceptions
    else:
        logger.exception(_func_info('{} =>'.format(exc)))
