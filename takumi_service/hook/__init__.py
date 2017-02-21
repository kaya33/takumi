# -*- coding: utf-8 -*-

"""
takumi_service.hook
~~~~~~~~~~~~~~~~~~~

For registering hooks.
"""

import collections


class Hook(object):
    """Represent a hook

    :param event: event name
    :param func: callback function
    """
    def __init__(self, event, func):
        self.event = event
        self.func = func

    def __call__(self, *args, **kwargs):
        self.func(*args, **kwargs)


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

    def register(self, hook):
        """Register a hook

        :param hook: a :class:`Hook` instance
        """
        self._registry[hook.event].append(hook.func)

hook_registry = _HookRegistry()


def define_hook(event):
    """Utility for hook definition

    :param event: event name
    """
    def deco(func):
        return Hook(event, func)
    return deco
