import argparse
import asyncio
import functools
import re
import operator
import inspect

from dataclasses import dataclass
from pathlib import Path
from typing import Union, List, Dict
from ptpython import embed
from prompt_toolkit import print_formatted_text, HTML

import aioipfs
from aioipfs.apis import SubAPI
import appdirs  # type: ignore

from omegaconf import OmegaConf

from .cli import configure


__version__ = '0.2.0'


@dataclass
class Context:
    client: aioipfs.AsyncIPFS
    interactive: bool = False


async def _cmd_wrapper(ctx: Context, method: str, *args, **kwargs):
    try:
        meth = operator.attrgetter(method)(ctx.client)
        assert meth

        if inspect.isasyncgenfunction(meth):
            # async generator
            _entries: List = []

            async for entry in meth(*args, **kwargs):
                _entries.append(entry)

            return _entries
        else:
            # coroutine
            return await meth(*args, **kwargs)
    except aioipfs.RPCAccessDenied:
        print('Access denied for this RPC endpoint! Check your credentials.')
    except (aioipfs.APIError, aioipfs.UnknownAPIError) as aerr:
        print(f'API error {aerr.code}: {aerr.message}')
    except AttributeError:
        print(f'No such client method: {method}')
    except BaseException:
        raise


def get_auth_helper(creds: str) -> Union[aioipfs.BasicAuth,
                                         aioipfs.BearerAuth]:
    ma = re.match(r'^basic:(.*?):(.*?)$', creds)
    if ma:
        return aioipfs.BasicAuth(ma.group(1), ma.group(2))

    ma = re.match(r'^bearer:(.*?)$', creds)
    if ma:
        return aioipfs.BearerAuth(ma.group(1))

    raise ValueError(f'Invalid RPC credentials value: {creds}')


async def start(args, cfg_dir: Path, data_dir: Path) -> None:
    cfg_path = cfg_dir.joinpath('bohort.yaml')

    if not cfg_path.exists():
        with open(cfg_path, 'wt') as f:
            OmegaConf.save(OmegaConf.create({
                'nodes': {}
            }), f)

    with open(cfg_path, 'rt') as f:
        cfg = OmegaConf.load(f)

    if args.save_node:
        assert re.match(r'^[\w_-]+$', args.save_node), \
            "Invalid node name format"

        if args.save_node in cfg.nodes:
            del cfg.nodes[args.save_node]

        ncfg = OmegaConf.create({
            'nodes': {
                args.save_node: {
                    'multiaddr': args.maddr,
                    'credentials': {
                        'default': args.creds
                    }
                }
            }
        })
        cfg = OmegaConf.merge(ncfg, cfg)

        with open(cfg_path, 'wt') as f:
            OmegaConf.save(cfg, f)

    if args.node:
        node, credid = tuple(args.node.split(
            ':')) if ':' in args.node else (args.node, None)

        ncfg = cfg.nodes.get(node)
        assert ncfg, 'Node configuration does not exist!'

        maddr = ncfg.multiaddr
        creds = ncfg.credentials.get(credid if credid else 'default')
    else:
        maddr = args.maddr
        creds = args.creds

    try:
        auth = get_auth_helper(creds) if creds else None

        async with aioipfs.AsyncIPFS(maddr=maddr, auth=auth) as client:
            ires = await client.core.id()

            if not ires:
                raise Exception(
                    f'Cannot connect to kubo node with RPC: {args.maddr}')

            peer_id = ires['ID']

            print_formatted_text(HTML(
                f'<violet>bohort v{__version__} '
                f'(aioipfs v{aioipfs.__version__})</violet>'))

            print_formatted_text(HTML(
                '<ansired>Remember to "await" your calls!</ansired>')
            )

            print_formatted_text(HTML(
                f'<seagreen>{maddr} ({peer_id})</seagreen>')
            )

            ctx = Context(client=client)

            clocals: Dict = {'ctx': ctx}

            for subapi_name in [name for name, _ in inspect.getmembers(client)
                                if isinstance(_, SubAPI)]:
                coros = [
                    name for name, _ in inspect.getmembers(
                        getattr(
                            client,
                            subapi_name
                        ), inspect.isroutine) if not name.startswith('_') and
                    name not in [
                        'add_generic',
                        'add_single',
                        'fetch_json',
                        'fetch_raw',
                        'fetch_text',
                        'handle_error',
                        'decode_error',
                        'mjson_decode',
                        'post']
                ]

                for mname in coros:
                    cmd = mname if subapi_name == 'core' else \
                        f'{subapi_name}_{mname}'
                    if cmd in clocals:
                        continue

                    clocals[cmd] = functools.partial(
                        _cmd_wrapper, ctx, f'{subapi_name}.{mname}'
                    )

            await embed(
                globals={},
                locals=clocals,
                return_asyncio_coroutine=True,
                patch_stdout=True,
                configure=configure,
                history_filename=args.history_path
            )  # type: ignore
    except aioipfs.RPCAccessDenied:
        print('RPC access denied!')
    except EOFError:
        pass
    except BaseException as err:
        raise err


def run_bohort():
    cfg_dir = Path(appdirs.user_config_dir('aioipfs')).joinpath('bohort')
    cfg_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(appdirs.user_data_dir('aioipfs')).joinpath('bohort')
    data_dir.mkdir(parents=True, exist_ok=True)

    history_path = data_dir.joinpath('history')

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--kubo-maddr',
        '--maddr',
        '-m',
        dest='maddr',
        default='/ip4/127.0.0.1/tcp/5001',
        help="kubo RPC API multiaddr"
    )
    parser.add_argument(
        '--creds',
        '--credentials',
        '-c',
        dest='creds',
        default=None,
        help='RPC authentication credentials'
    )
    parser.add_argument(
        '--history-path',
        dest='history_path',
        default=str(history_path),
        help='History file path'
    )
    parser.add_argument(
        '--save',
        dest='save_node',
        default=None,
        help='Save node configuration'
    )
    parser.add_argument(
        '--node',
        '-n',
        dest='node',
        help='Load node with this name from the config file',
        type=str
    )

    asyncio.run(start(parser.parse_args(), cfg_dir, data_dir))
