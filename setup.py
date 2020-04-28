from setuptools import find_packages, setup


# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()

setup(name='polyswarm-client',
      version='2.7.5',
      description='Client library to simplify interacting with a polyswarmd instance',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='PolySwarm Developers',
      author_email='info@polyswarm.io',
      url='https://github.com/polyswarm/polyswarm-client',
      license='MIT',
      include_package_data=True,
      install_requires=[
          'async-timeout<4.0,>=3.0',
          'aiohttp==3.6.2',
          'aiodns==1.2.0',
          'aioredis==1.3.1',
          'aioresponses==0.6.0',
          'aiorwlock==0.6.0',
          'asynctest==0.12.2',
          'backoff==1.10.0',
          'base58==0.2.5',
          'click~=7.0',
          "dataclasses==0.7; python_version == '3.6'",
          'jsonschema==3.0.2',
          'hypothesis==3.82.1',
          'polyswarm-artifact>=1.3.1',
          'pycryptodome>=3.4.7',
          'python-json-logger==0.1.9',
          'python-magic-bin==0.4.14;platform_system=="Windows"',
          'python-magic==0.4.15;platform_system=="Linux"',
          'web3==4.8.2',
          'websockets==6.0',
          'yara-python==3.7.0',
      ],
      package_dir={'': 'src'},
      packages=find_packages('src'),
      python_requires='>=3.6.5,<4',
      test_suite='tests',
      tests_require=[
          'coverage==4.5.1',
          'tox==3.4.0',
          'pytest==3.9.2',
          'pytest-asyncio==0.9.0',
          'pytest-cov==2.6.0',
          'pytest-timeout==1.3.2',
      ],
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
      ])
