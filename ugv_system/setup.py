#!/usr/bin/env python
from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

setup_args = generate_distutils_setup(
    packages=['pnp_sensor_monitor'],
    package_dir={'': 'src'},
    install_requires=['docker', 'requests', 'pyyaml']
)

setup(**setup_args)
