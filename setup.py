from setuptools import setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return f.read().splitlines()


setup(
    name='polyswarm-client',
    version='0.1',
    description=
    'Client library to simplify interacting with a polyswarmd instance',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/polyswarm-client',
    license='MIT',
    install_requires=parse_requirements(),
    include_package_data=True,
    packages=['polyswarmclient'],
    package_dir={'polyswarmclient': 'src/polyswarmclient'}
)
