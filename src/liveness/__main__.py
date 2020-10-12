import click
import logging
import sys
import warnings

from polyswarmclient.config import init_logging
from polyswarmclient.exceptions import FatalError
from polyswarmclient.liveness.local import LocalLivenessCheck


@click.command()
@click.option('--log', envvar='LOG_LEVEL', default='WARNING',
              help='Logging level')
@click.option('--log-format', envvar='LOG_FORMAT', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--loop-update-threshold', default=5,
              help='Maximum time since last loop iteration in polyswarm-client.Client before failing check')
@click.option('--average-bounty-wait-threshold', default=15,
              help='Maximum average time in blocks that bounties have been waiting before failing check')
def main(log, log_format, loop_update_threshold, average_bounty_wait_threshold):
    if 'liveliness' in sys.argv[0]:
        warnings.simplefilter('module', category=DeprecationWarning)
        warnings.warn('liveliness is deprecated, use liveness', DeprecationWarning)

    loglevel = getattr(logging, log.upper(), None)
    if not isinstance(loglevel, int):
        logging.error('invalid log level')
        raise FatalError('Invalid log level', 1)

    init_logging(['liveness'], log_format, loglevel)
    liveness_check = LocalLivenessCheck(loop_update_threshold, average_bounty_wait_threshold)
    if not liveness_check.check():
        raise FatalError('Liveness check failed', 1)


if __name__ == '__main__':
    main(sys.argv[1:])
