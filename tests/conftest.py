# -*- coding: utf-8 -*-

import mock
import pytest
from takumi_config import config


class MockConfig(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

reserved = {
    'thrift_file': 'tests/test.thrift',
    'thrift_protocol_class': ''
}

_config = MockConfig(reserved)


def mock_get(key, raises=False):
    return _config.get(key)


@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setattr(config, '__setattr__', _config.__setattr__)
    with mock.patch.object(config, 'get', mock_get):
        yield config
    _config.clear()
    _config.update(reserved)
