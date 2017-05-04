# -*- coding: utf-8 -*-

"""
takumi.testing
~~~~~~~~~~~~~~

This module is for testing. Nerver use the module in production environments.
"""

import functools
from io import BytesIO
from takumi_thrift import Client, Processor
from thriftpy.protocol.binary import TBinaryProtocol

from .service import TakumiService


class Socket(object):
    """Socket mock.
    """
    def __init__(self):
        self.rbuf = BytesIO()
        self.wbuf = BytesIO()

    def settimeout(self, timeout):
        pass

    def setsockopt(self, *args, **kwargs):
        pass

    def makefile(self, mode, bufsize=None):
        if 'w' in mode:
            return self.wbuf
        return self.rbuf

    def sendall(self, data):
        self.wbuf.write(data)

    def prepare_read(self):
        self.wbuf.seek(0)
        self.rbuf, self.wbuf = self.wbuf, self.rbuf

    def clear(self):
        for buf in (self.wbuf, self.rbuf):
            if buf.closed:
                continue
            buf.seek(0)
            buf.truncate(0)


class MemoryTransport(object):
    """A transport implementation based on memory.
    """
    def __init__(self, sock):
        self.sock = sock

    def is_open(self):
        return True

    def open(self):
        pass

    def close(self):
        self.sock.rbuf.close()
        self.sock.wbuf.close()

    def read(self, sz):
        return self.sock.rbuf.read(sz)

    def write(self, buf):
        self.sock.wbuf.write(buf)

    def flush(self):
        self.sock.wbuf.flush()

    def prepare_read(self):
        self.sock.prepare_read()

    def clear(self):
        self.sock.clear()


class MemoryProtocol(object):
    """Protocol based on memory transport.
    """
    def __init__(self, sock):
        self.trans = MemoryTransport(sock)

    def get_proto(self):
        return TBinaryProtocol(self.trans)

    def close(self):
        self.trans.close()


class ClientBase(object):
    """Base client for calling api.

    :param app: Takumi app
    """
    def __init__(self, app):
        service = TakumiService()
        service.set_handler(app)
        self._service = service.service_def
        self._processor = Processor(service.context, service.service_def,
                                    service.api_map)

        for api in self._service.thrift_services:
            if api.startswith('_'):
                continue
            setattr(self, api, functools.partial(self._call, api))

    def _call(self, api, *args, **kwargs):
        raise NotImplementedError


class ThriftClient(ClientBase):
    """Test client for thrift services.

    :Example:

    >>> c = ThriftClient(app)
    >>> c.ping()
    """
    def __init__(self, app, meta=None):
        super(ThriftClient, self).__init__(app)
        self._prot = MemoryProtocol(Socket()).get_proto()
        self._client = Client(self._service, self._prot, meta=meta or {})

    def _call(self, api, *args, **kwargs):
        try:
            self._client._send(api, *args, **kwargs)
            self._prot.trans.prepare_read()
            self._processor.process(self._prot, self._prot)
            self._prot.trans.prepare_read()
            return self._client._recv(api)
        finally:
            self._prot.trans.clear()
