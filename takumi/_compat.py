# -*- coding: utf-8 -*-

import sys
from thriftpy.protocol.exc import TProtocolException

PY2 = sys.version_info[0] == 2

if PY2:
    # Wrong syntax in py3
    exec('def reraise(tp, value, tb=None):\n raise tp, value, tb')

else:
    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value


try:
    from thriftpy.protocol.cybin import ProtocolError
    protocol_exceptions = (TProtocolException, ProtocolError)
except ImportError:
    protocol_exceptions = (TProtocolException,)
