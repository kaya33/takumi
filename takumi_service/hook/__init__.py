# -*- coding: utf-8 -*-

"""
takumi_service.hook
~~~~~~~~~~~~~~~~~~~

For registering hooks.
"""

import collections


class _HookRegistry(object):
    """Hook registry.

    The registry is a singleton. All threads share the same registry.
    """
    _registry = collections.defaultdict(list)

    def __getattr__(self, attr):
        if not attr.startswith('on_'):
            raise AttributeError('{} object has no attribute {}'.format(
                self.__class__.__name__, attr))
        # Remove leading `on_`
        hooks = self._registry[attr[3:]]
        return lambda *args, **kwargs: [hook(*args, **kwargs)
                                        for hook in hooks]

hook_registry = _HookRegistry()


def register_hook(event):
    """Register a hook. Hook is defined as a function with empty arguments.

    :param event: event name
    """
    def deco(func):
        _HookRegistry._registry[event].append(func)
        return func
    return deco
