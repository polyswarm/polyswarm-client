from setuptools import find_packages, setup


# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()


setup(
    name='polyswarm-client',
    version='2.7.3',
    description='Client library to simplify interacting with a polyswarmd instance',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/polyswarm-client',
    license='MIT',
    python_requires='>=3.6.5,<4',
    install_requires=[
        'aiodns==2.0.0',
        'aiohttp==3.6.2',
        'aioredis==1.3.1',
        'aioresponses==0.6.2',
        'aiorwlock==0.6.0',
        'backoff==1.10.0',
        'base58==0.2.5',
        'click==7.0',
        'dataclasses==0.7; python_version == "3.6"',
        'hexbytes==0.2.0',
        'jsonschema==3.2.0',
        'polyswarm-artifact>=1.3.2',
        'python-json-logger==0.1.11',
        'python-magic-bin==0.4.14;platform_system=="Windows"',
        'python-magic==0.4.15;platform_system=="Linux"',
        'web3==5.4.0',
        'websockets==8.1',
        'yara-python==3.11.0',
    ],
    include_package_data=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'ambassador=ambassador.__main__:main',
            'arbiter=arbiter.__main__:main',
            'liveliness=liveness.__main__:main',
            'liveness=liveness.__main__:main',
            'microengine=microengine.__main__:main',
            'verbatimdbgen=arbiter.verbatimdb.__main__:main',
            'balancemanager=balancemanager.__main__:cli',
            'worker=worker.__main__:main',
        ],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
    ]
)
