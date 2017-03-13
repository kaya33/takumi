# -*- coding: utf-8 -*-

import mock
import pytest
import os


@pytest.fixture(autouse=True)
def app_yaml():
    with mock.patch.dict(os.environ,
                         {'TAKUMI_APP_CONFIG_PATH': 'tests/app.yaml'}):
        yield
