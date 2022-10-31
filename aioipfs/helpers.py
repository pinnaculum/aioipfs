import functools
import json
import re
import sys
from multiaddr import Multiaddr
from distutils.version import StrictVersion
from contextlib import closing
import socket
import os.path

from urllib.parse import quote

from multiformats_cid import make_cid
from multiformats_cid import CIDv1
from multiformats_cid import CIDv0


try:
    import orjson
except ImportError:
    have_orjson = False
else:
    have_orjson = True


ARG_PARAM = 'arg'


def boolarg(arg):
    return str(arg).lower()


def quote_args(*args):
    # Used in the few cases where there are multiple 'arg=' URL params
    # that yarl can't handle at the moment
    quoted = ''

    if len(args) > 0:
        for arg in args:
            quoted += '&{0}={1}'.format(ARG_PARAM, quote(str(arg)))
        return quoted[1:]


def quote_dict(data):
    quoted = ''

    if not isinstance(data, dict):
        raise ValueError('quote_dict: need dictionary')

    for arg, value in data.items():
        if isinstance(value, list):
            for lvalue in value:
                quoted += '&{0}={1}'.format(arg, quote(str(lvalue)))
        elif isinstance(value, str):
            quoted += '&{0}={1}'.format(arg, quote(value))
        elif isinstance(value, int):
            quoted += '&{0}={1}'.format(arg, quote(str(value)))
        elif isinstance(value, bool):
            quoted += '&{0}={1}'.format(arg, quote(boolarg(value)))

    if len(quoted) > 0:
        return quoted[1:]


def decode_json(data: bytes):
    try:
        if not isinstance(data, bytes):
            raise TypeError('decode_json: invalid value type')

        if have_orjson:
            return orjson.loads(data.decode())
        else:
            return json.loads(data.decode())
    except Exception as exc:
        print('Could not read JSON object:', str(exc), file=sys.stderr)
        return None


def async_enterable(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        class AsyncEnterableInstance:
            async def __aenter__(self):
                self.context = await f(*args, **kwargs)
                return await self.context.__aenter__()

            async def __aexit__(self, *args, **kwargs):
                await self.context.__aexit__(*args, **kwargs)

            def __await__(self):
                return f(*args, **kwargs).__await__()

        return AsyncEnterableInstance()

    return wrapper


def maddr_tcp_explode(multi: Multiaddr) -> tuple:
    host, port = None, 0

    for proto in multi.protocols():
        if proto.name in ['ip4', 'ip6', 'dns4', 'dns6']:
            host = multi.value_for_protocol(proto.code)
        if proto.name == 'tcp':
            port = int(multi.value_for_protocol(proto.code))

    return host, port


def unusedTcpPort():
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]
    except Exception:
        return None


def p2p_addr_explode(addr: str) -> tuple:
    """
    Explode a P2P service endpoint address such as :

    /p2p/12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi/x/videocall/room1/1.0.0
    /p2p/12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi/x/test

    into its components, returning a tuple in the form

    (peerId, protoFull, protoVersion)

    protoFull can be passed to 'ipfs p2p dial'
    """

    peerIdRe = re.compile(r'([\w]){46,59}$')

    parts = addr.lstrip(os.path.sep).split(os.path.sep)
    try:
        assert parts.pop(0) == 'p2p'
        peerId = parts.pop(0)
        prefix = parts.pop(0)
        assert peerIdRe.match(peerId)
        assert prefix in ['x', 'y', 'z']

        pVersion = None
        protoA = [prefix]
        protoPart = parts.pop(0)
        protoA.append(protoPart)

        while protoPart:
            try:
                protoPart = parts.pop(0)
            except IndexError:
                break

            protoA.append(protoPart)

            try:
                v = StrictVersion(protoPart)
            except Exception:
                # No version
                pass
            else:
                # Found a version, should be last element
                pVersion = v
                assert len(parts) == 0
                break

        return peerId, os.path.sep + os.path.join(*protoA), pVersion
    except Exception:
        return None


def peerid_reencode(peerId: str,
                    base: str = 'base36',
                    multicodec: str = 'libp2p-key') -> str:
    """
    Encode a PeerId to a specific base
    """

    cid = make_cid(peerId)
    if not cid:
        return None

    if base in ['base32', 'base36']:
        return CIDv1(multicodec, cid.multihash).encode(base).decode()
    elif base in ['base58']:
        return str(CIDv0(cid.multihash))

    return None


def peerid_base32(peerId: str) -> str:
    """
    Convert any PeerId to a CIDv1 (base32)
    """
    return peerid_reencode(peerId, base='base32')


def peerid_base36(peerId: str) -> str:
    """
    Convert any PeerId to a CIDv1 (base36)
    """
    return peerid_reencode(peerId, base='base36')


def peerid_base58(peerId: str) -> str:
    """
    Convert any PeerId to a CIDv0
    """
    return peerid_reencode(peerId, base='base58')
