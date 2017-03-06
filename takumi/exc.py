# -*- coding: utf-8 -*-

"""
takumi_service.exc
~~~~~~~~~~~~~~~~~~

Takumi related Exceptin definitions.
"""


class TakumiException(Exception):
    """Base class for all Takumi exceptions
    """


class CloseConnectionError(TakumiException):
    """Exception for closing client connection
    """
