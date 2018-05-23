
import os, os.path, re
import sys
import codecs
from setuptools import setup, find_packages

PY_VER = sys.version_info

if PY_VER >= (3, 5):
    pass
else:
    raise RuntimeError("You need python3.5 or newer")

with codecs.open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'aioipfs', '__init__.py'), 'r', 'latin1') as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$",
                             fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')

setup(
    name='aioipfs',
    version=version,
    license='AGPL3',
    author='David Ferlier',
    url='https://gitlab.com/cipres/aioipfs',
    description='Asynchronous client library for IPFS',
    packages=['aioipfs'],
    include_package_data=False,
    scripts=['bin/asyncipfs', 'bin/ipfs-find'],
    install_requires=[
        'aiohttp>=2.0.0',
        'aiofiles',
        'async_generator>=1.0',
        'yarl',
        'base58',
        'tqdm'
        ],
    classifiers=[
        'Programming Language :: Python',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Topic :: System :: Filesystems',
    ],
    keywords=[
        'asyncio',
        'aiohttp',
        'ipfs'
    ],
)
