import click
import importlib.util
import logging

from polyswarmartifact import ArtifactType
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
@click.option('--log', default='WARNING', help='Logging level')
@click.option('--client-log', default='WARNING',
              help='PolySwarm Client log level')
@click.option('--polyswarmd-addr', envvar='POLYSWARMD_ADDR', default='api.polyswarm.network/v1/default',
              help='Address (host:port) of polyswarmd instance')
@click.option('--keyfile', envvar='KEYFILE', type=click.Path(exists=True), default='keyfile',
              help='Keystore file containing the private key to use with this arbiter')
@click.option('--password', envvar='PASSWORD', prompt=True, hide_input=True,
              help='Password to decrypt the keyfile with')
@click.option('--api-key', envvar='API_KEY', default='',
              help='API key to use with polyswarmd')
@click.option('--backend', envvar='BACKEND', required=True,
              help='Backend to use')
@click.option('--testing', default=0,
              help='Activate testing mode for integration testing, respond to N bounties then exit')
@click.option('--insecure-transport', is_flag=True,
              help='Connect to polyswarmd via http:// and ws://, mutually exclusive with --api-key')
@click.option('--chains', multiple=True, default=['side'],
              help='Chain(s) to operate on')
@click.option('--log-format', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--artifact-type', multiple=True, default=['file'],
              help='List of artifact types to scan')
def main(log, client_log, polyswarmd_addr, keyfile, password, api_key, backend, testing, insecure_transport, chains,
         log_format, artifact_type):
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

    artifact_types = None
    if artifact_type:
        artifact_types = [ArtifactType.from_string(artifact) for artifact in artifact_type]

    arbiter_class.connect(polyswarmd_addr, keyfile, password,
                          api_key=api_key, testing=testing,
                          insecure_transport=insecure_transport,
                          chains=set(chains),
                          artifact_types=artifact_types).run()


if __name__ == '__main__':
    main()
