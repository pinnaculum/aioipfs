.. _bohort:

======
bohort
======

*bohort* is an interactive REPL (*Read-Eval-Print-Loop*) command-line tool
(based on ptpython_) shipped
with aioipfs that allows the user to interact with kubo nodes and run
commands through the HTTP RPC API.

.. code-block:: shell

    pip install 'aioipfs[bohort]'

.. video:: https://bafybeicvpnbnmizmeoazw7klme4xkvczff4yrrjyb3wyookz523zvn6ane.ipfs.dweb.link/bohort-demo.mp4
   :autoplay:
   :width: 640
   :height: 480

=======
Running
=======

To connect to a kubo node, specify the multiaddr_ address of the RPC service,
and the (optional) RPC credentials (otherwise the default RPC multiaddr,
*/dns4/localhost/tcp/5001*, will be used).

.. code-block:: shell

    bohort --maddr /ip4/127.0.0.1/tcp/5001

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'basic:john:password123'

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'bearer:some-token'

You can save the configuration parameters for a node with *--save*. Load
a node configuration params by using *--node* or *--load*.

.. code-block:: shell

    bohort --maddr /ip4/127.0.0.1/tcp/5001 --creds 'basic:john:password123' --save local

    bohort --node local

If you don't want to use a history file, pass *--no-history*.

.. code-block:: shell

    bohort --no-history

=====
Usage
=====

All the aioipfs API coroutines are accessible from the REPL shell.

**Because any expression you type in the shell is passed to Python's eval(), to make an RPC call, you always need to "await" the call to any of the mapped coroutines.**

Here are some prompt command examples:

.. code-block:: shell

    await id()

    print((await id())['AgentVersion'])

    await bitswap_stat(verbose=True)

    await files_ls('/')

    await repo_gc()

    (await swarm_peers())['Peers'].pop()

    entries = await add('mydir', recursive=True, cid_version=1)

    await add_json({'whatever': 12345})

    await add_str('bohort')

If you do not store the result of a call in a variable, the result will be
pretty-printed to the console.

Configuration
=============

The configuration file location (on Posix platforms) is: **~/.config/aioipfs/bohort/bohort.yaml**

RPC methods
-----------

RPC params
^^^^^^^^^^

You can set the default params that will be passed to specific RPC methods
by defining the default coroutine keyword arguments for each method:

.. code-block:: yaml

    rpc_methods:
      core.add:
        defaults:
          recursive: true
          cid_version: 1
      core.add_str:
        defaults:
          cid_version: 1
      key.gen:
        defaults:
          type: 'ed25519'
          size: 4096

If you pass a parameter for which you've set a default in the config, the default
value won't be used.

Timeout
^^^^^^^

You can set a timeout (in seconds) for each RPC method:

.. code-block:: yaml

    rpc_methods:
      core.ls:
        timeout: 60

REPL settings
^^^^^^^^^^^^^

.. code-block:: yaml

    repl:
      cursor_shape: Blink block
      input_prompt_color: ansigreen
      output_prompt_color: ansiyellow

      # Possible values: POP_UP, MULTI_COLUMN, TOOLBAR or NONE
      completion_visualisation: POP_UP

      color_scheme: default
      show_signature: true
      enable_history_search: true
      enable_auto_suggest: true
      complete_while_typing: false
      confirm_exit: false

Check out ptpython's
`config.py example <https://github.com/prompt-toolkit/ptpython/blob/master/examples/ptpython_config/config.py>`_ for a description of all the settings.


REPL toolkit documentation
--------------------------

See ptpython_ and prompt-toolkit_.

.. _multiaddr: https://multiformats.io/multiaddr/
.. _ptpython: https://github.com/prompt-toolkit/ptpython
.. _prompt-toolkit: https://python-prompt-toolkit.readthedocs.io/en/master
