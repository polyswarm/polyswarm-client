import click
import importlib.util
import logging
import warnings
import multiprocessing

from polyswarmclient.exceptions import FatalError
from worker import Worker
from polyswarmclient.config import init_logging, validate_apikey

logger = logging.getLogger(__name__)  # Initialize logger


def choose_backend(backend):
    """Resolves scanner name string to implementation

    Args:
        backend (str): Name of the backend to load, either one of the predefined implementations or the name of a module
        to load

        (module:ClassName syntax or default of module:Scanner)
    Returns:
        (Class): Scanner class of the selected implementation
    Raises:
        (Exception): If backend is not found
    """
    backend_list = backend.split(':')
    module_name_string = backend_list[0]

    # determine if this string is a module that can be imported as-is or as sub-module of the worker package
    mod_spec = importlib.util.find_spec('microengine.{0}'.format(module_name_string)) or \
        importlib.util.find_spec(module_name_string)
    if mod_spec is None:
        raise Exception('Scanner backend `{0}` cannot be imported as a python module.'.format(backend))

    # have valid module that can be imported, so import it.
    scanner_module = importlib.import_module(mod_spec.name)

    # find Scanner class in this module
    if hasattr(scanner_module, 'Scanner'):
        scanner_class = scanner_module.Scanner
    elif len(backend_list) == 2 and hasattr(scanner_module, backend_list[1]):
        scanner_class = getattr(scanner_module, backend_list[1])
    else:
        raise Exception('No scanner backend found {0}'.format(backend))

    return scanner_module.__name__, scanner_class


@click.command()
@click.option('--log', envvar='LOG_LEVEL', default='WARNING',
              help='Logging level')
@click.option('--client-log', envvar='CLIENT_LOG_LEVEL', default='WARNING',
              help='PolySwarm Client log level')
@click.option('--redis-addr', envvar='REDIS_ADDR', default='localhost:6379',
              help='Address (host:port) of polyswarmd instance')
@click.option('--queue', envvar='QUEUE', required=True,
              help='Queue to listen for jobs on')
@click.option('--api-key', envvar='API_KEY', default='',  callback=validate_apikey,
              help='API key to use with polyswarmd')
@click.option('--backend', envvar='BACKEND', required=True,
              help='Backend to use')
@click.option('--tasks', envvar='TASKS', default=0,
              help='Deprecated')
@click.option('--download-limit', envvar='DOWNLOAD_LIMIT', default=multiprocessing.cpu_count(),
              help='Limit number of simultaneous file downloads')
@click.option('--scan-limit', envvar='SCAN_LIMIT', default=multiprocessing.cpu_count(),
              help='Limit number of simultaneous scans')
@click.option('--testing', default=0,
              help='Activate testing mode for integration testing, respond to N bounties and N offers then exit')
@click.option('--log-format', envvar='LOG_FORMAT', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--scan_time_requirement', envvar='SCAN_TIME_REQUIREMENT', default=3,
              help='Minimum time in seconds required to scan an artifact. Jobs with less time will be ignored')
@click.option('--daily-rate-limit', envvar='DAILY_RATE_LIMIT', default=None,
              help='Number of scans allowed per day')
@click.option('--hourly-rate-limit', envvar='HOURLY_RATE_LIMIT', default=None,
              help='Number of scans allowed per hour')
@click.option('--minutely-rate-limit', envvar='MINUTELY_RATE_LIMIT', default=None,
              help='Number of scans allowed per minute')
@click.option('--secondly-rate-limit', envvar='SECONDLY_RATE_LIMIT', default=None,
              help='Number of scans allowed per second')
@click.option('--allow-key-over-http', is_flag=True, envvar='ALLOW_KEY_OVER_HTTP',
              help='Force api keys over http (Not Recommended)')
def main(log, client_log, redis_addr, queue, backend, tasks, download_limit, scan_limit, api_key, testing, log_format,
         scan_time_requirement, daily_rate_limit, hourly_rate_limit, minutely_rate_limit, secondly_rate_limit,
         allow_key_over_http):
    """Entrypoint for the worker driver
    """
    if tasks != 0:
        warnings.warn('Use of --tasks or TASKS is deprecated', DeprecationWarning)

    tasks = 0 if download_limit == 0 or scan_limit == 0 else max(download_limit, scan_limit)
    loglevel = getattr(logging, log.upper(), None)
    clientlevel = getattr(logging, client_log.upper(), None)
    if not isinstance(loglevel, int) or not isinstance(clientlevel, int):
        logging.error('invalid log level')
        raise FatalError('Invalid log level', 1)

    logger_name, scanner_class = choose_backend(backend)

    scanner = scanner_class()
    init_logging(['worker', 'microengine', logger_name], log_format, loglevel)
    init_logging(['polyswarmclient'], log_format, clientlevel)

    logger.info('Running worker with %s tasks', tasks if tasks > 0 else 'unlimited')
    worker = Worker(redis_addr, queue, tasks, download_limit, scan_limit, api_key, testing, scanner,
                    scan_time_requirement, daily_rate_limit, hourly_rate_limit, minutely_rate_limit, secondly_rate_limit,
                    allow_key_over_http)
    worker.run()


if __name__ == '__main__':
    main()
