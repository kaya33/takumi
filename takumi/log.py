# -*- coding: utf-8 -*-

"""
takumi.log
~~~~~~~~~~

This module implements log configuration.

Hook definition:

    - init_process  Config logs
"""

import sys
import logging
import logging.config
from copy import deepcopy

from .hook import define_hook

CONF = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': None,
    'loggers': {},
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        }
    },
    'formatters': {
        'console': {
            'format': ('%(asctime)s %(levelname)-6s '
                       '%(name)s[%(process)d] %(message)s'),
        },
        'syslog': {
            'format': '%(name)s[%(process)d]: %(message)s',
        },
    },
}

SYSLOG_HANDLER = {
    'level': 'INFO',
    'class': 'logging.handlers.SysLogHandler',
    'address': '/dev/log',
    'facility': 'local6',
    'formatter': 'syslog',
}


def _logger(handlers, level='INFO', propagate=True):
    return {
        'handlers': handlers,
        'propagate': propagate,
        'level': level
    }


def _console(name):
    conf = deepcopy(CONF)
    conf['root'] = _logger(['console'])
    conf['loggers'][name] = _logger(['console'], propagate=False)
    return conf


def _syslog(name):
    conf = deepcopy(CONF)
    conf['root'] = _logger(['syslog'])
    conf['loggers'][name] = _logger(['syslog'], propagate=False)
    conf['handlers']['syslog'] = SYSLOG_HANDLER
    return conf


@define_hook(event='after_load')
def config_log():
    """Config log according to app name and environment.
    """
    from takumi_config import config

    name = config.app_name
    env = config.env

    if env == 'dev' or sys.platform == 'darwin' or config.syslog_disabled:
        conf = _console(name)
    else:
        conf = _syslog(name)
    logging.config.dictConfig(conf)


class MetaAdapter(logging.LoggerAdapter):
    """Add meta to logging message

    meta format: [{client_name}/{client_version} {client_addr} {extra}]
    missing component will be filled with '-'
    """
    def process(self, msg, kwargs):
        if 'ctx' not in self.extra:
            return super(MetaAdapter, self).process(msg, kwargs)

        ctx = self.extra['ctx']
        env = ctx.get('env', {})
        meta = ctx.get('meta', {})
        components = [
            '/'.join((meta.get('client_name', '-'),
                      meta.get('client_version', '-'))),
            env.get('client_addr', '-'),
        ]
        if 'log_extra' in ctx:
            components.append(ctx['log_extra'])
        return '[{}] {}'.format(' '.join(components), msg), kwargs
