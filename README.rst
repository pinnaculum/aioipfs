=======
aioipfs
=======

:info: Asynchronous IPFS_ client library

**aioipfs** is a python3 library providing an asynchronous API for IPFS_.
Supported python versions: *3.6*, *3.7*, *3.8*, *3.9*

This library supports the
`RPC API specifications <https://docs.ipfs.tech/reference/kubo/rpc>`_
for kubo_ version *0.15.0*.

See `the documentation here <https://aioipfs.readthedocs.io/en/latest>`_.

.. image:: https://github.com/pinnaculum/aioipfs/workflows/aioipfs-build/badge.svg
    :target: https://github.com/pinnaculum/aioipfs

.. image:: https://gitlab.com/cipres/aioipfs/badges/master/pipeline.svg

Installation
============

.. code-block:: shell

    pip install aioipfs

Usage
=====

Client instantiation
--------------------

The recommended way to specify the kubo node's RPC API address is
to pass a multiaddr_.

.. code-block:: python

    client = aioipfs.AsyncIPFS(maddr='/ip4/127.0.0.1/tcp/5001')

    client = aioipfs.AsyncIPFS(maddr='/dns4/localhost/tcp/5001')

You can also pass a *multiaddr.Multiaddr* instance.

.. code-block:: python

    from multiaddr import Multiaddr

    client = aioipfs.AsyncIPFS(maddr=Multiaddr('/ip4/127.0.0.1/tcp/5001'))

Otherwise just pass *host* and *port* separately:

.. code-block:: python

    client = aioipfs.AsyncIPFS(host='localhost', port=5001)

    client = aioipfs.AsyncIPFS(host='::1', port=5201)

Get an IPFS resource
--------------------

.. code-block:: python

    import sys
    import asyncio

    import aioipfs

    async def get(ipfshash):
        client = aioipfs.AsyncIPFS()
        await client.get(ipfshash, dstdir='.')
        await client.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(get(sys.argv[1]))

Add some files
--------------

This example will import all files and directories specified on the command
line. Note that the **add** API function is an asynchronous generator and
therefore should be used with the *async for* syntax.

.. code-block:: python

    import sys
    import asyncio

    import aioipfs

    async def add_files(files):
        client = aioipfs.AsyncIPFS()

        async for added_file in client.add(*files, recursive=True):
            print('Imported file {0}, CID: {1}'.format(
                added_file['Name'], added_file['Hash']))

        await client.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(add_files(sys.argv[1:]))

You can also use the async list generator syntax:

.. code-block:: python

    cids = [entry['Hash'] async for entry in client.add(dir_path)]

Pubsub service
--------------

.. code-block:: python

    async def pubsub_serve(topic):
        async with aioipfs.AsyncIPFS() as cli:
            async for message in cli.pubsub.sub(topic):
                print('Received message from', message['from'])
                await cli.pubsub.pub(topic, message['data'])

Features
========

Async file writing on get operations
------------------------------------

The **aiofiles** library is used to asynchronously write data retrieved from
the IPFS daemon when using the */api/v0/get* API call, to avoid blocking the
event loop. TAR extraction is done in asyncio's threadpool.

Requirements
============

- Python >= 3.6, <= 3.9
- aiohttp_
- aiofiles_
- py-multibase_
- yarl_

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aiofiles: https://pypi.python.org/pypi/aiofiles
.. _multiaddr: https://multiformats.io/multiaddr/
.. _py-multibase: https://pypi.python.org/pypi/py-multibase
.. _yarl: https://pypi.python.org/pypi/yarl
.. _IPFS: https://ipfs.io
.. _kubo: https://github.com/ipfs/kubo

License
=======

**aioipfs** is offered under the GNU Lesser GPL3 (LGPL3) license.
