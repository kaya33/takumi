takumi: Thrift service framework
================================

This package defines the interfaces for writing Takumi thrift services.

Example
-------

To define a simple app:

.. code-block:: python

    from takumi import Takumi

    app = Takumi('TestService')

    @app.api
    def say_hello(name):
        return 'Hello ' + name
