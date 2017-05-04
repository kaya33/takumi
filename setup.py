#! /usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


setup(
    name='takumi',
    version='0.1.4',
    description='Takumi service framework',
    long_description=open("README.rst").read(),
    author="Eleme Lab",
    author_email="imaralla@icloud.com",
    packages=find_packages(),
    package_data={'': ['LICENSE', 'README.rst']},
    url='https://github.com/elemepi/takumi',
    install_requires=[
        'takumi-config',
        'takumi-thrift',
        'thriftpy>=0.3.9',
        'gevent>=1.2.1',
    ],
)
