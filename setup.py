#!/usr/bin/env python3

import os

from pyinstaller_setuptools import setup
from setuptools import find_packages

# When making a debian package from this package, inline requirements just confuses the debian
# tools, so simply leave them out if the DH_INTERNAL_BUILDFLAGS env-variable is set.
if os.getenv("DH_INTERNAL_BUILDFLAGS"):
    KW_ARGS={}
else:
    KW_ARGS={
        "install_requires":[
             'configargparse',
             'prometheus-client',
             'haproxy-log-analysis>4.1',
             'tailhead'
        ],
        "setup_requires":['pytest-runner'],
        "tests_require":['pytest-sugar', 'pytest-html', 'pytest-cov', 'pytest'],
    }

setup(
    name="prometheus-haproxy-log-exporter",
    version="0.0.2",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'prometheus-haproxy-log-exporter = prometheus_haproxy_log_exporter.cli:main',
        ],
    },
    **KW_ARGS
)
