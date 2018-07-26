=======
aioipfs
=======

:info: Asynchronous client library for IPFS_

The **aioipfs** Python package provides asynchronous access to the IPFS_ API,
using Python 3.5's async/await mechanism.

Installation
============

PIP package coming soon, for now install with setup.py:

.. code-block:: shell

    python setup.py install

Usage examples
==============

Get an IPFS resource
--------------------

.. code-block:: python

    import sys
    import asyncio

    import aioipfs

    async def get(ipfshash):
        client = aioipfs.AsyncIPFS()
        await client.get(ipfshash)
        await client.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(get(sys.argv[1]))
    loop.close()

Included tools
==============

asyncipfs
---------

The  **asyncipfs** program implements a few IPFS basic functions (add, get,
pin, log etc..) with **aioipfs**. You can give multiple hashes parameters and they
will be processed concurrently, for example:

.. code-block:: shell
    
    asyncipfs get hash1 hash2 hash3

ipfs-find
---------

**ipfs-find** allows you to search for content on any IPFS node you have access
to. It can be useful to recover the hashes of something you've added a while
ago. Usage:

.. code-block:: shell

    usage: ipfs-find [-h] [--apihost str] [--apiport str] [-j] [-i] [--name NAME]
                     [--type TYPE] [--contains CONTAINS]

    optional arguments:
      -h, --help           show this help message and exit
      --apihost str        IPFS API host
      --apiport str        IPFS API port
      -j                   JSON output
      -i                   Case-insensitive match
      --name NAME          Match object name
      --type TYPE          Match object type ('d' for directory, 'f' for file)
      --contains CONTAINS  Match object content

**Example**: search for files whose name matches 'dmenu.*.c' and which contains
'size_t', with output in JSON:

.. code-block:: shell

    ipfs-find  --type f --name 'dmenu.*.c$' --contains 'size_t' -j
    [
        {
            "Name": "dmenu.c",
            "Hash": "Qmb7MGgtGzWn2NQ1PbxhXjZCwNxxuJUSRfMfSL1ZFW2Fwk",
            "Size": 16926,
            "Type": 2
        }
    ]

Features
========

Async file writing on get operations
------------------------------------

The **aiofiles** library is used to asynchronously write data retrieved from
the IPFS daemon when using the /api/v0/get API call, to avoid blocking the
event loop. TAR extraction is done in asyncio's threadpool.

Requirements
============

- Python >= 3.5.3
- async-timeout_
- async-generator_
- aiohttp_
- aiofiles_
- yarl_

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aiofiles: https://pypi.python.org/pypi/aiofiles
.. _yarl: https://pypi.python.org/pypi/yarl
.. _async-timeout: https://pypi.python.org/pypi/async_timeout
.. _async-generator: https://pypi.python.org/pypi/async_generator
.. _IPFS: https://ipfs.io

License
=======

**aioipfs** is offered under the GNU GPL3 license.

Authors
=======

David Ferlier
