#! /usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


setup(
    name='takumi_service',
    version='0.1.0',
    description='Takumi service',
    long_description=open("README.rst").read(),
    author="Eleme Lab",
    author_email="imaralla@icloud.com",
    packages=find_packages(),
    package_data={'': ['LICENSE', 'README.rst']},
    url='https://github.com/elemecreativelab/takumi-service',
    install_requires=[
        'thriftpy>=0.3.9',
        'gevent>=1.2.1',
    ],
    dependency_links=[
        'git+git://github.com/elemepi/takumi-config.git#egg=takumi_config',
    ],
)
