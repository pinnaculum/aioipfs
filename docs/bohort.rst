.. _bohort:

======
bohort
======

.. toctree::
   :maxdepth: 2
   :name: mastertoc

*bohort* is an interactive REPL (*Read-Eval-Print-Loop*) command-line tool
(based on ptpython_) shipped
with aioipfs that allows the user to interact with kubo nodes and run
commands through the HTTP RPC API.

.. code-block:: shell

    pip install 'aioipfs[bohort]'

Running
-------

To connect to a kubo node, specify the multiaddr_ address of the RPC service,
and the (optional) RPC credentials.

.. code-block:: shell

    bohort --maddr /ip4/127.0.0.1/tcp/5001

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'basic:john:password123'

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'bearer:some-token'

You can save the configuration parameters for a node with *--save*. Load
a node configuration params by using *--node*.

.. code-block:: shell

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'basic:john:password123' --save local

    bohort --node local

Usage
-----

All the aioipfs API coroutines are accessible from the REPL shell.

**Because any expression you type in the shell is passed to Python's eval(), to make an RPC call, you always need to "await" the call to any of the mapped coroutines.**

Here are some prompt command examples:

.. code-block:: shell

    await id()

    await bitswap_stat(verbose=True)

    await files_ls('/')

    await repo_gc()

    (await swarm_peers())['Peers'].pop()

    entries = await add('mydir', recursive=True, cid_version=1)

If you do not store the result of a call in a variable, the result will be
pretty-printed to the console.

.. _multiaddr: https://multiformats.io/multiaddr/
.. _ptpython: https://github.com/prompt-toolkit/ptpython
