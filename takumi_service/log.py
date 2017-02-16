# -*- coding: utf-8 -*-

"""
takumi_service.log
~~~~~~~~~~~~~~~~~~

This module implements log configuration.

Implemented hooks:

    - init_process  Config logs
"""

import sys
import logging
from copy import deepcopy

from .hook import register_hook

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


@register_hook(event='init_process')
def config_log():
    """Config log according to app name and environment.
    """
    from takumi_config import config

    name = config.app_name
    env = config.env.name

    if env == 'dev' or sys.platform == 'darwin' or config.syslog_disabled:
        conf = _console(name)
    else:
        conf = _syslog(name)
    logging.config.dictConfig(conf)
