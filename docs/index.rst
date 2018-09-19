.. aioipfs documentation master file, created by
   sphinx-quickstart on Mon Sep  3 00:02:10 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=======
aioipfs
=======

Asynchronous IPFS client API for Python3's asyncio.

.. toctree::
   :maxdepth: 2
   :name: mastertoc

   api

.. module:: aioipfs
.. currentmodule:: aioipfs

Async IPFS client
=================

Creating an :class:`~aioipfs.AsyncIPFS` client::

    import aioipfs

    client = aioipfs.AsyncIPFS()

which would assume you are connecting to the IPFS daemon on *localhost* on port
5001 (default IPFS API port). You can specify alternative parameters::

    client = aioipfs.AsyncIPFS(host='10.0.12.3', port=5003)

Maximum HTTP connections and read timeout parameters::

    client = aioipfs.AsyncIPFS(host='localhost', port=5008, conns_max=20)

    client = aioipfs.AsyncIPFS(host='localhost', port=5008, read_timeout=30)

The API is divided between the various IPFS subsystems, each subsystem has its
own namespace/attribute inside the *AsyncIPFS* object, for example *client.pin*
for the PIN api, *client.files* for the files/MFS API, etc ..

All API functions will raise an :class:`~APIError` if there's an exception
raised during the request.

Async context manager
---------------------

You can use an async context manager in your code::

    async with aioipfs.AsyncIPFS() as client:
        async for reply in client.ping(peer_id):
            ...

Closing
-------

When finished you should always call :meth:`AsyncIPFS.close` on your client::

    await client.close()

Core API
========

.. attribute:: aioipfs.AsyncIPFS.core
    
    Gives access to the :class:`~api.CoreAPI` 

Adding files
-------------

Add files to the IPFS repository with the :meth:`api.CoreAPI.add` async
generator::

    async for added in client.core.add('file1.txt', '/usr/local/src',
            recursive=True):
        print(added['Hash'])

    async for added in client.core.add(['one', 'two', 'three'],
            wrap_with_directory=True):
        ...

Entries yielded by the generator are as returned by the IPFS daemon,
dictionaries with *Name*, *Hash* and *Size* keys.

Adding bytes
------------

Add some bytes with :meth:`api.CoreAPI.add_bytes`::

    >>> entry = await client.core.add_bytes(b'ABCD')
    {'Name': 'QmZ655k2oftYnsocBxqTWzDer3GNui2XQTtcA4ZUbhpz5N', 'Hash': 'QmZ655k2oftYnsocBxqTWzDer3GNui2XQTtcA4ZUbhpz5N', 'Size': '12'}

Adding string data
------------------

Add a UTF-8 string with :meth:`api.CoreAPI.add_str`::

    entry = await client.core.add_str('ABCD')

Getting IPFS objects
--------------------

Download IPFS objects with :meth:`api.CoreAPI.get`::

    await client.core.get('QmRGqvWK44oWu8re5whp43P2M7j5XEDLHmPB3wncYFmCNg')

    await client.core.get('QmRGqvWK44oWu8re5whp43P2M7j5XEDLHmPB3wncYFmCNg',
        dstdir='/tmp')

Cat
---

Use :meth:`api.CoreAPI.cat` to get an object's raw data::
    
    bytes = await client.core.cat(multihash)

Listing a path/multihash
------------------------

Use :meth:`api.CoreAPI.ls` for listing::

    listing = await client.core.ls(path)

Node information
----------------

Get IPFS node information::

    info = await client.core.id()

Pin API
=======

.. attribute:: aioipfs.AsyncIPFS.pin

    Gives access to the :class:`~api.PinAPI` 

Pinning a multihash or an IPFS path::

    async for pinned in client.pin.add(multihash):
        print('Pin progress', pinned['Progress'])

Listing the pinned multihashes::

    pinned = await client.pin.ls()

Unpin with::

    await client.pin.rm(path)

P2P API
=======

.. attribute:: aioipfs.AsyncIPFS.p2p

    Gives access to the :class:`~api.P2PAPI` 

Block API
=========

.. attribute:: aioipfs.AsyncIPFS.block

    Gives access to the :class:`~api.BlockAPI` 

Config API
==========

.. attribute:: aioipfs.AsyncIPFS.config

    Gives access to the :class:`~api.ConfigAPI` 

Pubsub API
==========

.. attribute:: aioipfs.AsyncIPFS.pubsub

    Gives access to the :class:`~api.PubsubAPI` 

Bitswap API
===========

.. attribute:: aioipfs.AsyncIPFS.bitswap

    Gives access to the :class:`~api.BitswapAPI` 

Bootstrap API
=============

.. attribute:: aioipfs.AsyncIPFS.bootstrap

    Gives access to the :class:`~api.BootstrapAPI` 

DAG API
=======

.. attribute:: aioipfs.AsyncIPFS.dag

    Gives access to the :class:`~api.DagAPI` 

DHT API
=======

.. attribute:: aioipfs.AsyncIPFS.dht

    Gives access to the :class:`~api.DhtAPI` 

Files API
=========

.. attribute:: aioipfs.AsyncIPFS.files

    Gives access to the :class:`~api.FilesAPI` 

Filestore API
=============

.. attribute:: aioipfs.AsyncIPFS.filestore

    Gives access to the :class:`~api.FilestoreAPI` 

Keys API
========

.. attribute:: aioipfs.AsyncIPFS.key

    Gives access to the :class:`~api.KeyAPI` 

Log API
=======

.. attribute:: aioipfs.AsyncIPFS.log

    Gives access to the :class:`~api.LogAPI` 

Access the IPFS event log with::

    import pprint
    async for msg in client.log.tail():
        print(pprint.pprint(msg))

Name API
========

.. attribute:: aioipfs.AsyncIPFS.name

    Gives access to the :class:`~api.NameAPI` 

Object API
==========

.. attribute:: aioipfs.AsyncIPFS.object

    Gives access to the :class:`~api.ObjectAPI` 

Refs API
========

.. attribute:: aioipfs.AsyncIPFS.refs

    Gives access to the :class:`~api.RefsAPI` 

Repo API
========

.. attribute:: aioipfs.AsyncIPFS.repo

    Gives access to the :class:`~api.RepoAPI` 

Swarm API
=========

.. attribute:: aioipfs.AsyncIPFS.swarm

    Gives access to the :class:`~api.SwarmAPI` 

TAR API
=========

.. attribute:: aioipfs.AsyncIPFS.tar

    Gives access to the :class:`~api.TarAPI` 

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
