# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
from future_lain_cli import __version__

ENTRY_POINTS = """
[console_scripts]
legacy_lain = lain_cli.lain:main
lain = future_lain_cli.lain:main
"""

requirements = [
    # legacy lain
    'arrow',
    'jinja2',
    'six>=1.9.0',
    'PyYAML>=3.12',
    'argh>=0.26.1',
    'argcomplete>=1.9.3',
    'humanfriendly>=4.16.1',
    'requests',
    'tabulate>=0.7.5',
    'jenkinsapi==0.3.3',
    'einplus_lain_sdk>=3.2.4',
    'einplus_entryclient>=2.4.1',
    # future lain
    'click>=7.0',
    'jinja2>=2.10.3',

]

setup(
    name="einplus_lain_cli",
    python_requires='>=3.7',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    entry_points=ENTRY_POINTS,
    install_requires=requirements,
    zip_safe=False,
)
