import os
import os.path
import re
import sys
import codecs

from setuptools import setup

PY_VER = sys.version_info

if PY_VER >= (3, 6):
    pass
else:
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

setup(
    name='aioipfs',
    version=version,
    license='LGPLv3',
    author='David Ferlier',
    author_email='galacteek@protonmail.com',
    url='https://gitlab.com/cipres/aioipfs',
    description='Asynchronous IPFS client library',
    long_description=long_description,
    packages=['aioipfs'],
    include_package_data=False,
    install_requires=install_reqs,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',  # noqa
        'Topic :: System :: Filesystems'
    ],
    keywords=[
        'asyncio',
        'aiohttp',
        'ipfs'
    ]
)
