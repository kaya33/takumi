# -*- coding: utf-8 -*-

import pytest


def test_registry():
    from takumi.hook import define_hook, HookRegistry

    hook_registry = HookRegistry()

    @define_hook(event='test_registry_hook')
    def demo_hook(hello, world):
        return ' '.join([hello, world])
    hook_registry.register(demo_hook)

    ret = hook_registry.on_test_registry_hook('hello', 'world')
    assert ret == ['hello world']

    with pytest.raises(AttributeError) as exc_info:
        hook_registry.invalid_hook()
    assert str(exc_info.value) == \
        'HookRegistry object has no attribute invalid_hook'
    assert hook_registry.on_extra_hook() == []
