takumi-service: Takumi thrift service implementation
====================================================

This package defines the interfaces for writing Takumi thrift services.

Example
-------

To define a simple app:

.. code-block:: python

    from takumi_service.service import ServiceHandler

    app = ServiceHandler('TestService')

    @app.api
    def say_hello(name):
        return 'Hello ' + name
