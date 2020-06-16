# PolySwarm Client Library

[![pipeline status](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/pipeline.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![coverage report](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/coverage.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![Read the Docs Build Status](https://readthedocs.org/projects/polyswarm-client/badge/?version=latest)](https://polyswarm-client.readthedocs.io/en/latest/)


## Overview

For the convenience of those who wish to join the PolySwarm marketplace, this is
a client library to simplify interacting with a polyswarmd instance from your Python code.

It includes:

* abstract classes for ambassador, arbiter, and microengine implementations
* exemplar ambassador, arbiter, and microengine implementations
* helper classes

For important changes releases, see the [Release History](https://github.com/polyswarm/polyswarm-client/blob/master/HISTORY.md).

## Installation

You need python3 >= 3.6.5 and pip >= 20.0.
Then use pip to install polyswarm-client.

```bash
pip install polyswarm-client
```

## Documentation

We have extensive documentation on how to use this package available in [our docs](https://docs.polyswarm.io).

## For Developers

### Running Tests

Install all app dependencies:

```bash
pip install -rrequirements.txt
```

Install all test dependencies:

```bash
pip install -rrequirements-test.txt
```

Run all tests:

```bash
pytest
```

### Updating VCR cassettes

- Run `polyswarmd-fast` by following the instructions in the project's `README.md` file.
- Delete the cassette files.
- Re-run all tests
