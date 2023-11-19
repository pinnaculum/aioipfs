import os
import os.path
import re
import sys
import codecs

from setuptools import setup
from setuptools import find_packages

if sys.version_info < (3, 6):
    raise RuntimeError("You need python3.6 or newer")

with codecs.open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'aioipfs', '__init__.py'), 'r', 'latin1') as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$",
                             fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')

with open("README.rst", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    install_reqs = f.read().splitlines()

with open('requirements-dev.txt') as f:
    install_test_reqs = f.read().splitlines()

setup(
    name='aioipfs',
    version=version,
    license='LGPLv3',
    author='cipres',
    author_email='alkaline@gmx.co.uk',
    url='https://gitlab.com/cipres/aioipfs',
    description='Asynchronous IPFS client library',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    packages=find_packages(exclude=['tests']),
    include_package_data=False,
    install_requires=install_reqs,
    extras_require={
        'orjson': ['orjson>=3.0'],
        'car': ['ipfs-car-decoder==0.1.1'],
        'test': install_test_reqs
    },
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',  # noqa
        'Topic :: System :: Filesystems',
        'Topic :: Communications :: File Sharing'
    ],
    keywords=[
        'asyncio',
        'aiohttp',
        'ipfs'
    ]
)
