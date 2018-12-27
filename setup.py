# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
from lain_cli import __version__

ENTRY_POINTS = """
[console_scripts]
lain = lain_cli.lain:main
"""

requirements = [
    'six>=1.9.0',
    'PyYAML>=3.12',
    'argh>=0.26.1',
    'argcomplete>=1.9.3',
    'humanfriendly>=4.16.1',
    'requests',
    'tabulate>=0.7.5',
    'einplus_lain_sdk>=3.0.0b6',
    'einplus_entryclient>=2.4.1',
]


setup(
    name="einplus_lain_cli",
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    entry_points=ENTRY_POINTS,
    install_requires=requirements
)
