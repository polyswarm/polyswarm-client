import re
from pathlib import Path
from setuptools import find_packages, setup

# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()


def requirements_entries(*entries) -> 'List[str]':
    """Returns a list of requirements matching each 'entries'"""
    reqs = [
        r.strip() for f in ('requirements.txt', 'requirements-test.txt')
        for r in Path(f).read_text().splitlines() if not r.startswith('#')
    ]
    return [
        # find line starting w/ `entry` followed by any non-word char except . & -.
        next(filter(re.compile('^' + re.escape(entry) + r'\b(?![-.])').match, reqs))
        for entry in entries
    ]


setup(name='polyswarm-client',
      version='2.11.5',
      description='Client library to simplify interacting with a polyswarmd instance',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='PolySwarm Developers',
      author_email='info@polyswarm.io',
      url='https://github.com/polyswarm/polyswarm-client',
      license='MIT',
      include_package_data=True,
      install_requires=requirements_entries(
          'aiohttp',
          'aiodns',
          'aioredis',
          'aioresponses',
          'aiorwlock',
          'cachetools',
          'asynctest',
          'backoff',
          'base58',
          'click',
          'hexbytes',
          'polyswarm-artifact',
          'polyswarm-transaction',
          'pycryptodome',
          'python-json-logger',
          'python-magic-bin',
          'python-magic',
          'web3',
          'websockets',
          'yara-python',
      ),
      package_dir={'': 'src'},
      packages=find_packages('src'),
      python_requires='>=3.6.5,<4',
      test_suite='tests',
      tests_require=requirements_entries(
          'asynctest',
          'coverage',
          'deepdiff',
          'hypothesis',
          'pytest',
          'pytest-asyncio',
          'pytest-cov',
          'pytest-timeout',
          'pytest-mock',
          'tox',
      ),
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
          "Programming Language :: Python :: 3.8",
      ])
