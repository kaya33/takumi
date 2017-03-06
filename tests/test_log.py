# -*- coding: utf-8 -*-

import mock


def test_log_config_logger():
    from takumi.log import _logger
    ret = _logger(['console'], 'WARN', propagate=False)
    assert ret == {
        'handlers': ['console'],
        'propagate': False,
        'level': 'WARN'
    }


def test_log_console():
    from takumi.log import _console

    ret = _console('test_app')
    assert ret == {
        'disable_existing_loggers': False,
        'root': {
            'propagate': True,
            'level': 'INFO',
            'handlers': ['console']
        },
        'formatters': {
            'console': {
                'format': ('%(asctime)s %(levelname)-6s '
                           '%(name)s[%(process)d] %(message)s')
            },
            'syslog': {
                'format': '%(name)s[%(process)d]: %(message)s'
            }
        },
        'loggers': {
            'test_app': {
                'propagate': False,
                'level': 'INFO',
                'handlers': ['console']
            }
        },
        'handlers': {
            'console': {
                'formatter': 'console',
                'class': 'logging.StreamHandler',
                'level': 'DEBUG'
            }
        },
        'version': 1
    }


def test_log_syslog():
    from takumi.log import _syslog

    ret = _syslog('test_app')
    assert ret == {
        'root': {
            'propagate': True,
            'handlers': ['syslog'],
            'level': 'INFO'
        },
        'version': 1,
        'handlers': {
            'syslog': {
                'class': 'logging.handlers.SysLogHandler',
                'formatter': 'syslog',
                'address': '/dev/log',
                'level': 'INFO',
                'facility': 'local6'
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'console',
                'level': 'DEBUG'
            }
        },
        'loggers': {
            'test_app': {
                'propagate': False,
                'handlers': ['syslog'],
                'level': 'INFO'
            }
        },
        'disable_existing_loggers': False,
        'formatters': {
            'syslog': {
                'format': '%(name)s[%(process)d]: %(message)s'
            },
            'console': {
                'format': ('%(asctime)s %(levelname)-6s '
                           '%(name)s[%(process)d] %(message)s')
            }
        }
    }


def test_config_log(monkeypatch):
    from takumi.log import config_log
    import takumi_config
    import logging.config
    import takumi.log
    import sys

    mock_config = type('_config', (object,), {})
    mock_config.syslog_disabled = False
    mock_config.env = type('_env', (object,), {})

    monkeypatch.setattr(sys, 'platform', 'linux')

    config_log_func = config_log.func

    def _mock():
        mock_dict_config = mock.Mock()
        monkeypatch.setattr(logging.config, 'dictConfig', mock_dict_config)
        mock_console = mock.Mock()
        monkeypatch.setattr(takumi.log, '_console', mock_console)
        mock_syslog = mock.Mock()
        monkeypatch.setattr(takumi.log, '_syslog', mock_syslog)
        return mock_dict_config, mock_console, mock_syslog

    with mock.patch.object(takumi_config, 'config', mock_config):
        mock_config.app_name = 'test_app'
        mock_config.env.name = 'dev'

        a, b, c = _mock()
        config_log_func()
        a.assert_called()
        b.assert_called_with('test_app')
        c.assert_not_called()

        mock_config.env.name = 'prod'
        a, b, c = _mock()
        config_log_func()
        a.assert_called()
        b.assert_not_called()
        c.assert_called_with('test_app')


def test_log_adapter():
    import logging
    from takumi.log import MetaAdapter
    import sys
    ctx = {}
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger = MetaAdapter(logging.getLogger('takumi'), {'ctx': ctx})
    logger_class = logging.getLoggerClass()
    with mock.patch.object(logger_class, '_log') as mock_log:
        logger.info('hello world')
    mock_log.assert_called_with(20, '[-/- -] hello world', ())

    ctx['meta'] = {
        'client_name': 'test_client',
        'client_version': '1.0.1'
    }
    ctx['env'] = {'client_addr': '127.0.0.1'}
    with mock.patch.object(logger_class, '_log') as mock_log:
        logger.info('hello world')
    mock_log.assert_called_with(
        20, '[test_client/1.0.1 127.0.0.1] hello world', ())

    ctx['log_extra'] = '353456436546 xxxx yyyy'
    with mock.patch.object(logger_class, '_log') as mock_log:
        logger.info('hello world')
    mock_log.assert_called_with(
        20, '[test_client/1.0.1 127.0.0.1 353456436546 xxxx yyyy] hello world',
        ())
