#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return f.read().splitlines()


# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()


setup(
    name='polyswarm-client',
    version='0.2.0',
    description='Client library to simplify interacting with a polyswarmd instance',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/polyswarm-client',
    license='MIT',
    python_requires='>=3.5.6,<4',
    install_requires=parse_requirements(),
    include_package_data=True,
    packages=['polyswarmclient', 'ambassador', 'arbiter', 'microengine', 'arbiter.verbatimdb', 'balancemanager'],
    package_dir={
        'polyswarmclient': 'src/polyswarmclient',
        'ambassador': 'src/ambassador',
        'arbiter': 'src/arbiter',
        'microengine': 'src/microengine',
        'arbiter.verbatimdb': 'src/arbiter/verbatimdb',
        'balancemanager': 'src/balancemanager'
    },
    entry_points={
        'console_scripts': [
            'ambassador=ambassador.__main__:main',
            'arbiter=arbiter.__main__:main',
            'microengine=microengine.__main__:main',
            'verbatimdbgen=arbiter.verbatimdb.__main__:main',
            'balancemanager=balancemanager.__main__:cli',
            'reporter=polyswarmclient.reporter:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
    ]
)
