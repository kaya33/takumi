# -*- coding: utf-8 -*-

"""
takumi.exc
~~~~~~~~~~

Takumi related Exceptin definitions.
"""


class TakumiException(Exception):
    """Base class for all Takumi exceptions
    """


class CloseConnectionError(TakumiException):
    """Exception for closing client connection
    """


class TimeoutException(TakumiException):
    """Raised when api call timeout
    """
    def __init__(self, timeout):
        self.timeout = timeout

    def __str__(self):
        return 'Timeout after {} seconds'.format(self.timeout)
