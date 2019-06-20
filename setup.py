# -*- coding: utf-8 -*-
# Copyright (c) 2019 Luca Pinello
# GPLv3 license
#This code is based on the javascript version available here https://github.com/bpowers/btscale


import os
from setuptools import setup
from setuptools import find_packages

import re

version = re.search(
    	'^__version__\s*=\s*"(.*)"',
    	open('pyacaia/__init__.py').read(),
    	re.M
    	).group(1)

setup(
    name='pyacaia',
    version=version,
    description='A Python module to interact with ACAIA scales via bluetooth (BLE)',
    url='https://github.com/lucapinello/pyacaia',
    author='Luca Pinello',
    license='GPLv3',
    packages=find_packages(),
    install_requires=[
        'bluepy', #pygatt is also supported
    ]
)
