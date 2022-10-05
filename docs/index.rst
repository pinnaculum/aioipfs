.. aioipfs documentation master file, created by
   sphinx-quickstart on Mon Sep  3 00:02:10 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=======
aioipfs
=======

Asynchronous IPFS client API for Python3's asyncio.

.. toctree::
   :maxdepth: 5
   :name: mastertoc

   api

.. module:: aioipfs
.. currentmodule:: aioipfs

Installation
============

.. code-block:: shell

    pip install aioipfs

If you want to use orjson_ to decode JSON messages:

.. code-block:: shell

    pip install 'aioipfs[orjson]'

Async IPFS client
=================

To create an :class:`~aioipfs.AsyncIPFS` client instance it's
recommended to specify the node's RPC API address with a multiaddr_::

    import aioipfs

    client = aioipfs.AsyncIPFS(maddr='/ip4/127.0.0.1/tcp/5001')

    client = aioipfs.AsyncIPFS(maddr='/dns4/localhost/tcp/5001')

The default constructor assumes that the kubo_ node you want to
connect to is *localhost* on port *5001* (use the *host* and *port*
keyword arguments to set different values)::

    client = aioipfs.AsyncIPFS()

    client = aioipfs.AsyncIPFS(host='10.0.12.3', port=5003)

Maximum HTTP connections and read timeout parameters::

    client = aioipfs.AsyncIPFS(host='localhost', port=5008, conns_max=20)

    client = aioipfs.AsyncIPFS(host='localhost', port=5008, read_timeout=30)


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

API sectioning
==============

The kubo_ (formerly called *go-ipfs*) RPC HTTP API provides many
endpoints which allow to access the different subsystems of the IPFS
daemon. You can read the 
`RPC API specifications here <https://docs.ipfs.tech/reference/kubo/rpc>`_.

**Important**: The **aioipfs** client API closely follows kubo_'s RPC
endpoints path hierarchy, as each subsystem has its own
namespace/attribute inside the *AsyncIPFS* client object, for example:

- *client.core* for the :class:`~api.CoreAPI` 
- *client.pin* for the :class:`~apis.pin.PinAPI`
- *client.pin.remote* for the :class:`~apis.pin.PinRemoteAPI`
- *client.files* for the :class:`~api.FilesAPI` 
- *client.pubsub* for the :class:`~apis.pubsub.PubSubAPI`

etc ...  

All API functions will raise an :class:`~aioipfs.exceptions.APIError`
(or a more specific exception) if there's an error raised during the request.

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

    cids = [entry['Hash'] async for entry in client.add(dir_path)]

Entries yielded by the generator are as returned by the IPFS daemon,
dictionaries with *Name*, *Hash* and *Size* keys.

Since kubo *v0.16.0*, you can import content and link the resulting
object in the MFS in the same RPC call, by using the *to_files*
string argument, which should the path in the MFS for the link::

    async for added in client.core.add('file1.txt', to_files='/file1.txt'):
        print(added['Hash'])

Adding bytes
------------

Add some bytes with :meth:`api.CoreAPI.add_bytes`::

    >>> entry = await client.core.add_bytes(b'ABCD')
    {'Name': 'QmZ655k2oftYnsocBxqTWzDer3GNui2XQTtcA4ZUbhpz5N', 'Hash': 'QmZ655k2oftYnsocBxqTWzDer3GNui2XQTtcA4ZUbhpz5N', 'Size': '12'}

    entry = await client.core.add_bytes('ABCD', to_files='/abcd')

Adding string data
------------------

Add a UTF-8 string with :meth:`api.CoreAPI.add_str`::

    entry = await client.core.add_str('ABCD')

    entry = await client.core.add_str('ABCD', to_files='/abcd')

Getting IPFS objects
--------------------

Download IPFS objects with :meth:`api.CoreAPI.get`::

    await client.core.get('QmRGqvWK44oWu8re5whp43P2M7j5XEDLHmPB3wncYFmCNg')

    await client.core.get('QmRGqvWK44oWu8re5whp43P2M7j5XEDLHmPB3wncYFmCNg',
        dstdir='/tmp')

Cat
---

Use :meth:`api.CoreAPI.cat` to get an object's raw data::
    
    bytes = await client.core.cat(cid)

Listing a path or CID
---------------------

Use :meth:`api.CoreAPI.ls` for listing::

    listing = await client.core.ls(path)

Node information
----------------

Get IPFS node information::

    info = await client.core.id()

Block API
=========

.. attribute:: aioipfs.AsyncIPFS.block

    Gives access to the :class:`~api.BlockAPI` 

Bitswap API
===========

.. attribute:: aioipfs.AsyncIPFS.bitswap

    Gives access to the :class:`~api.BitswapAPI` 

Bootstrap API
=============

.. attribute:: aioipfs.AsyncIPFS.bootstrap

    Gives access to the :class:`~api.BootstrapAPI` 

Config API
==========

.. attribute:: aioipfs.AsyncIPFS.config

    Gives access to the :class:`~api.ConfigAPI` 

CID API
=======

.. attribute:: aioipfs.AsyncIPFS.cid

    Gives access to the :class:`~api.CidAPI`

DAG API
=======

.. attribute:: aioipfs.AsyncIPFS.dag

    Gives access to the :class:`~api.DagAPI` 

DHT API
=======

.. attribute:: aioipfs.AsyncIPFS.dht

    Gives access to the :class:`~api.DhtAPI` 

Diag API
========

.. attribute:: aioipfs.AsyncIPFS.diag

    Gives access to the :class:`~api.DiagAPI` 

File API
========

.. attribute:: aioipfs.AsyncIPFS.file

    Gives access to the :class:`~api.FileAPI` 

Files API
=========

.. attribute:: aioipfs.AsyncIPFS.files

    Gives access to the :class:`~api.FilesAPI` 

Filestore API
=============

.. attribute:: aioipfs.AsyncIPFS.filestore

    Gives access to the :class:`~api.FilestoreAPI` 

Key API
=======

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

Multibase API
=============

.. attribute:: aioipfs.AsyncIPFS.multibase

    Gives access to the :class:`~apis.multibase.MultibaseAPI` 

Name API
========

.. attribute:: aioipfs.AsyncIPFS.name

    Gives access to the :class:`~api.NameAPI` 

Object API
==========

.. attribute:: aioipfs.AsyncIPFS.object

    Gives access to the :class:`~api.ObjectAPI` 

P2P API
=======

.. attribute:: aioipfs.AsyncIPFS.p2p

    Gives access to the :class:`~api.P2PAPI` 

Pin API
=======

.. attribute:: aioipfs.AsyncIPFS.pin

    Gives access to the :class:`~apis.pin.PinAPI`

Pinning a CID or an IPFS path::

    async for pinned in client.pin.add(cid):
        print('Pin progress', pinned['Progress'])

Listing the pinned objects::

    pinned = await client.pin.ls()

Unpin with::

    await client.pin.rm(path)

Pin remote API
==============

.. attribute:: aioipfs.AsyncIPFS.pin.remote

    Gives access to the :class:`~apis.pin.PinRemoteAPI`

Pubsub API
==========

.. attribute:: aioipfs.AsyncIPFS.pubsub

    Gives access to the :class:`~apis.pubsub.PubSubAPI`

Refs API
========

.. attribute:: aioipfs.AsyncIPFS.refs

    Gives access to the :class:`~api.RefsAPI` 

Repo API
========

.. attribute:: aioipfs.AsyncIPFS.repo

    Gives access to the :class:`~api.RepoAPI` 

Routing API
===========

.. attribute:: aioipfs.AsyncIPFS.routing

    Gives access to the :class:`~api.RoutingAPI`

Swarm API
=========

.. attribute:: aioipfs.AsyncIPFS.swarm

    Gives access to the :class:`~apis.swarm.SwarmAPI` 

Swarm Peering API
=================

.. attribute:: aioipfs.AsyncIPFS.swarm.peering

    Gives access to the :class:`~apis.swarm.SwarmPeeringAPI` 

TAR API
=======

.. attribute:: aioipfs.AsyncIPFS.tar

    Gives access to the :class:`~api.TarAPI` 

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _multiaddr: https://multiformats.io/multiaddr/
.. _kubo: https://github.com/ipfs/kubo
.. _orjson: https://github.com/ijl/orjson
