import click
import importlib.util
import logging
import sys

from polyswarmclient.config import init_logging
from polyswarmclient.exceptions import FatalError

logger = logging.getLogger(__name__)  # Initialize logger


def choose_backend(backend):
    """Resolves arbiter name string to implementation

    Args:
        backend (str): Name of the backend to load, either one of the
          predefined implementations or the name of a module to load
          (module:ClassName syntax or default of module:Arbiter)
    Returns:
        (Class): Arbiter class of the selected implementation
    Raises:
        (Exception): If backend is not found
    """
    backend_list = backend.split(':')
    module_name_string = backend_list[0]

    # determine if this string is a module that can be imported as-is or as sub-module of the arbiter package
    mod_spec = importlib.util.find_spec(module_name_string) or importlib.util.find_spec(
        'arbiter.{0}'.format(module_name_string))
    if mod_spec is None:
        raise Exception('Arbiter backend `{0}` cannot be imported as a python module.'.format(backend))

    # have valid module that can be imported, so import it.
    arbiter_module = importlib.import_module(mod_spec.name)

    # find Arbiter class in this module
    if hasattr(arbiter_module, 'Arbiter'):
        arbiter_class = arbiter_module.Arbiter
    elif len(backend_list) == 2 and hasattr(arbiter_module, backend_list[1]):
        arbiter_class = getattr(arbiter_module, backend_list[1])
    else:
        raise Exception('No arbiter backend found {0}'.format(backend))

    return arbiter_module.__name__, arbiter_class


@click.command()
@click.option('--log', envvar='LOG_LEVEL', default='WARNING', help='Logging level')
@click.option('--client-log', envvar='CLIENT_LOG_LEVEL', default='WARNING',
              help='PolySwarm Client log level')
@click.option('--polyswarmd-addr', envvar='POLYSWARMD_ADDR', default='https://api.polyswarm.network/v1/default',
              help='Deprecated')
@click.option('--keyfile', envvar='KEYFILE', type=click.Path(),
              help='Deprecated')
@click.option('--password', envvar='PASSWORD',
              help='Deprecated')
@click.option('--api-key', envvar='API_KEY', default='',
              help='API key to use with polyswarmd')
@click.option('--webhook_secret', envvar='WEBHOOK_SECRET', default='',
              help='Secret to authenticate incoming requests from polyswarm')
@click.option('--backend', envvar='BACKEND', required=True,
              help='Backend to use')
@click.option('--testing', default=0,
              help='Activate testing mode for integration testing, respond to N bounties then exit')
@click.option('--allow-key-over-http', is_flag=True, envvar='ALLOW_KEY_OVER_HTTP',
              help='Force api keys over http (Not Recommended)')
@click.option('--chains', multiple=True, default=['side'],
              help='Chain(s) to operate on')
@click.option('--log-format', envvar='LOG_FORMAT', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--artifact-type', multiple=True, default=['file'],
              help='Deprecated')
@click.option('--host', envvar='HOST', default='0.0.0.0',
              help='Host address to run the server')
@click.option('--port', envvar='PORT', default='8080',
              help='Port to listen for webhooks')
def main(log, client_log, polyswarmd_addr, keyfile, password, api_key, webhook_secret, backend, testing,
         allow_key_over_http, chains, log_format, artifact_type, host, port):
    """
    Entrypoint for the arbiter driver
    """
    loglevel = getattr(logging, log.upper(), None)
    clientlevel = getattr(logging, client_log.upper(), None)
    if not isinstance(loglevel, int) or not isinstance(clientlevel, int):
        logging.error('invalid log level')
        raise FatalError('Invalid log level', 1)

    logger_name, arbiter_class = choose_backend(backend)

    init_logging(['arbiter', logger_name], log_format, loglevel)
    init_logging(['polyswarmclient'], log_format, clientlevel)

    arbiter_class.connect(host=host, port=port, api_key=api_key, webhook_secret=webhook_secret).run()


if __name__ == '__main__':
    main(sys.argv[1:])
