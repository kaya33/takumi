# -*- coding: utf-8 -*-


def test_thrift_client():
    from takumi import Takumi
    from takumi.testing import ThriftClient

    app = Takumi('TestService')

    @app.api
    def say_hello(name):
        return 'Hello ' + name

    c = ThriftClient(app)
    assert c.say_hello('world').value == 'Hello world'
