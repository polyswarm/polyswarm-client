import click

from arbiter.verbatimdb.db import generate_db
from polyswarmclient.config import init_logging


@click.command()
@click.option('--malicious', type=click.Path(exists=True), default='./artifacts/malicious',
              help='Input directory of malicious files')
@click.option('--benign', type=click.Path(exists=True), default='./artifacts/benign',
              help='Input directory of benign files')
@click.option('--output', type=click.Path(), default='./artifacts/truth.db',
              help='Output database file.')
@click.option('--log_format', envvar='LOG_FORMAT', default='text',
              help='Log format. Can be `json` or `text` (default)')
def main(malicious, benign, output, log_format):
    init_logging([], log_format)
    generate_db(output, malicious, benign)


if __name__ == '__main__':
    main()
