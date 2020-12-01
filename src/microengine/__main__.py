from typing import Tuple, Type

import click
import importlib.util
import logging
import sys
from polyswarmclient.abstractmicroengine import AbstractMicroengine

from polyswarmclient.config import init_logging, validate_apikey
from polyswarmclient.exceptions import FatalError

logger = logging.getLogger(__name__)  # Initialize logger


def choose_backend(backend) -> Tuple[str, Type[AbstractMicroengine]]:
    """Resolves microengine name string to implementation

    Args:
        backend (str): Name of the backend to load, either one of the predefined
            implementations or the name of a module to load
            (module:ClassName syntax or default of module:Microengine)
    Returns:
        (Class): Microengine class of the selected implementation
    Raises:
        (Exception): If backend is not found
    """
    backend_list = backend.split(':')
    module_name_string = backend_list[0]

    # determine if this string is a module that can be imported as-is or as sub-module of the microengine package
    mod_spec = importlib.util.find_spec(module_name_string) or importlib.util.find_spec(
        'microengine.{0}'.format(module_name_string))
    if mod_spec is None:
        raise Exception('Microengine backend `{0}` cannot be imported as a python module.'.format(backend))

    # have valid module that can be imported, so import it.
    microengine_module = importlib.import_module(mod_spec.name)

    # find Microengine class in this module
    if hasattr(microengine_module, 'Microengine'):
        microengine_class = microengine_module.Microengine
    elif len(backend_list) == 2 and hasattr(microengine_module, backend_list[1]):
        microengine_class = getattr(microengine_module, backend_list[1])
    else:
        raise Exception('No microengine backend found {0}'.format(backend))

    return microengine_module.__name__, microengine_class


def choose_bid_strategy(bid_strategy):
    """Resolves bid strategy name string to implementation
    Args:
        bid_strategy (str): Name of the bid strategy to load, either one of the predefined
            implementations or the name of a module to load
            (module:ClassName syntax or default of )
    Returns:
        (Class): Microengine class of the selected implementation
    Raises:
        (Exception): If backend is not found
    """
    # determine if this string is a module that can be imported as-is or as sub-module of the microengine package
    mod_spec = importlib.util.find_spec(bid_strategy) or \
        importlib.util.find_spec(f'microengine.bidstrategy.{bid_strategy}')
    if mod_spec is None:
        raise Exception('Bid strategy `{0}` cannot be imported as a python module.'.format(bid_strategy))

    # have valid module that can be imported, so import it.
    bid_strategy_module = importlib.import_module(mod_spec.name)

    # find BidStrategy class in this module
    if hasattr(bid_strategy_module, 'BidStrategy'):
        bid_strategy_class = bid_strategy_module.BidStrategy
    else:
        raise Exception('No bid strategy found {0}'.format(bid_strategy))

    return bid_strategy_module.__name__, bid_strategy_class


@click.command()
@click.option('--log', envvar='LOG_LEVEL', default='WARNING',
              help='App Log level')
@click.option('--client-log', envvar='CLIENT_LOG_LEVEL', default='WARNING',
              help='PolySwarm Client log level')
@click.option('--polyswarmd-addr', envvar='POLYSWARMD_ADDR', default='https://api.polyswarm.network/v1/default',
              help='Deprecated')
@click.option('--keyfile', envvar='KEYFILE', type=click.Path(),
              help='Deprecated')
@click.option('--password', envvar='PASSWORD',
              help='Deprecated')
@click.option('--api-key', envvar='API_KEY', default='',
              callback=validate_apikey,
              help='API key to use with polyswarmd')
@click.option('--backend', envvar='BACKEND', required=True,
              help='Backend to use')
@click.option('--testing', default=0,
              help='Deprecated')
@click.option('--allow-key-over-http', is_flag=True, envvar='ALLOW_KEY_OVER_HTTP',
              help='Force api keys over http (Not Recommended)')
@click.option('--chains', multiple=True, default=['side'],
              help='Chain(s) to operate on')
@click.option('--log-format', envvar='LOG_FORMAT', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--artifact-type', multiple=True, default=['file'],
              help='Deprecated')
@click.option('--bid-strategy', envvar='BID_STRATEGY', default='default',
              help='Deprecated')
@click.option('--filter', multiple=True, default=[],
              help='Deprecated')
@click.option('--confidence', multiple=True, default=[],
              help='Deprecated')
@click.option('--host', envvar='HOST', default='0.0.0.0',
              help='Host address to run the server')
@click.option('--port', envvar='PORT', default='8080',
              help='Port to listen for webhooks')
def main(log, client_log, polyswarmd_addr, keyfile, password, api_key, backend, testing, allow_key_over_http, chains,
         log_format, artifact_type, bid_strategy, filter, confidence, host, port):
    """ Entrypoint for the microengine driver
    """
    loglevel = getattr(logging, log.upper(), None)
    clientlevel = getattr(logging, client_log.upper(), None)
    if not isinstance(loglevel, int) or not isinstance(clientlevel, int):
        logging.error('invalid log level')
        raise FatalError('Invalid log level', 1)

    logger_name, microengine_class = choose_backend(backend)
    bid_logger_name, bid_strategy_class = choose_bid_strategy(bid_strategy)

    init_logging(['microengine', logger_name], log_format, loglevel)
    init_logging(['polyswarmclient'], log_format, clientlevel)

    microengine_class.connect(host=host, port=port, api_key=api_key, bid_strategy=bid_strategy_class()).run()


if __name__ == '__main__':
    main(sys.argv[1:])
