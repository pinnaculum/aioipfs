import json
import os.path
import tarfile
import tempfile
import sys
import base58
import base64
from urllib.parse import quote

import asyncio
import aiofiles
import aioipfs

from aiohttp import payload
from aiohttp.web_exceptions import (HTTPError,
                                    HTTPInternalServerError,
                                    HTTPServerError, HTTPBadRequest)

from . import multi

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


def decode_json(data):
    if not data:
        return None
    try:
        json_obj = json.loads(data.decode())
    except Exception as exc:
        print(data, file=sys.stderr)
        print('Could not read JSON object:', str(exc), file=sys.stderr)
        return None

    return json_obj


HTTP_ERROR_CODES = [
    HTTPInternalServerError.status_code,
    HTTPBadRequest.status_code,
    HTTPError.status_code,
    HTTPServerError.status_code
]

DEFAULT_TIMEOUT = 60 * 60


class SubAPI(object):
    """
    Master class for all classes implementing API functions

    :param driver: the AsyncIPFS instance
    """

    def __init__(self, driver):
        self.driver = driver

    def url(self, path):
        return self.driver.api_endpoint(path)

    def decode_error(self, errormsg):
        try:
            decoded_json = json.loads(errormsg)
            msg = decoded_json['Message']
            code = decoded_json['Code']
            return msg, code
        except Exception:
            return None, None

    async def fetch_text(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, textdata = response.status, await response.text()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(textdata)
                raise aioipfs.APIError(code=code, message=msg,
                                       http_status=status)
            return textdata

    async def fetch_raw(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, data = response.status, await response.read()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(data)
                raise aioipfs.APIError(code=code, message=msg,
                                       http_status=status)
            return data

    async def fetch_json(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, jsondata = response.status, await response.json()
            if status in HTTP_ERROR_CODES:
                if 'Message' in jsondata and 'Code' in jsondata:
                    raise aioipfs.APIError(
                        code=jsondata['Code'],
                        message=jsondata['Message'],
                        http_status=status)
                else:
                    raise aioipfs.UnknownAPIError()

            return jsondata

    async def post(self, url, data, headers={}, params={},
                   timeout=DEFAULT_TIMEOUT, outformat='text'):
        async with self.driver.session.post(url, data=data,
                                            headers=headers,
                                            params=params) as response:
            if response.status in HTTP_ERROR_CODES:
                errtext = await response.read()
                raise aioipfs.APIError(message=errtext,
                                       http_status=response.status)

            if outformat == 'text':
                return await response.text()
            elif outformat == 'json':
                return await response.json()
            else:
                raise Exception('Unknown output format {0}'.format(outformat))

    async def mjson_decode(self, url, method='get', data=None,
                           params=None, headers=None,
                           new_session=False,
                           timeout=60.0 * 60,
                           read_timeout=60.0 * 10):
        """
        Multiple JSON objects response decoder (async generator), used for
        the API endpoints which return multiple JSON messages

        :param str method: http method, get or post
        :param data: data, for POST only
        :param params: http params
        """

        kwargs = {'params': params if isinstance(params, dict) else {}}

        if new_session is True:
            session = self.driver.get_session(
                conn_timeout=timeout,
                read_timeout=read_timeout
            )
        else:
            session = self.driver.session

        if method not in ['get', 'post']:
            raise ValueError('mjson_decode: unknown method')

        if method == 'post':
            if data is not None:
                kwargs['data'] = data

        if isinstance(headers, dict):
            kwargs['headers'] = headers

        async with getattr(session, method)(url, **kwargs) as response:
            async for raw_message in response.content:
                message = decode_json(raw_message)

                if message is not None:
                    if 'Message' in message and 'Code' in message:
                        raise aioipfs.APIError(code=message['Code'],
                                               message=message['Message'],
                                               http_status=response.status)
                    else:
                        yield message

                await asyncio.sleep(0)

        if new_session is True:
            await session.close()


class P2PAPI(SubAPI):
    """
    P2P API.

    Note: go-ipfs v0.4.18 introduced some changes in the P2P subsystem
    and some endpoints were renamed. Agent version detection is done
    in the affected API calls to maintain compatibility.
    """
    async def listener_open(self, protocol, address,
                            allow_custom_protocol=False):
        """
        Open a P2P listener

        :param str protocol: protocol name associated with the listener
        :param str address: address for the listener, in multiaddr format
        """

        api_post0418 = await self.driver.agent_version_post0418()

        if api_post0418 is True:
            url = self.url('p2p/listen')
            params = quote_dict({
                ARG_PARAM: [protocol, address],
                'allow-custom-protocol': boolarg(allow_custom_protocol)
            })
        else:
            url = self.url('p2p/listener/open')
            params = quote_args(protocol, address)

        return await self.fetch_json(url, params=params)

    async def listener_close(self, protocol, listen_address=None,
                             target_address=None, all=False):
        """
        Close a previously opened P2P listener

        :param str protocol: protocol name associated with the listener
        :param bool all: if True, closes all listeners on the node
        """

        api_post0418 = await self.driver.agent_version_post0418()

        if api_post0418 is True:
            url = self.url('p2p/close')
            params = {
                'protocol': protocol,
                'all': boolarg(all)
            }

            if listen_address:
                params['listen-address'] = listen_address
            if target_address:
                params['target-address'] = target_address
        else:
            url = self.url('p2p/listener/close')
            params = {
                ARG_PARAM: protocol,
                'all': boolarg(all)
            }

        return await self.fetch_json(url, params=params)

    async def listener_ls(self, headers=False):
        """
        List P2P listeners

        :param bool headers: print all headers (HandlerID, Protocol, ...)
        """

        api_post0418 = await self.driver.agent_version_post0418()

        if api_post0418 is True:
            url = self.url('p2p/ls')
        else:
            url = self.url('p2p/listener/ls')

        return await self.fetch_json(url,
                                     params={'headers': boolarg(headers)})

    async def stream_dial(self, protocol, laddress, target,
                          allow_custom_protocol=False):
        """
        Dial to a P2P listener.

        :param str peer: Remote Peer ID
        :param str protocol: protocol identifier
        :param str address: multiaddr to listen for connection/s
            (default: /ip4/127.0.0.1/tcp/0)
        """

        api_post0418 = await self.driver.agent_version_post0418()

        if api_post0418 is True:
            url = self.url('p2p/forward')
            params = quote_dict({
                ARG_PARAM: [protocol, laddress, target],
                'allow-custom-protocol': boolarg(allow_custom_protocol)
            })
        else:
            url = self.url('p2p/stream/dial')
            args = [
                target,
                protocol,
                laddress] if laddress else [
                target,
                protocol]
            params = quote_args(*args)

        return await self.fetch_json(url, params=params)

    async def stream_close(self, stream_id=None, all=False):
        """
        Close active P2P stream.
        """

        if stream_id and all is False:
            params = {
                ARG_PARAM: stream_id,
            }
        elif all is True:
            params = {
                'all': boolarg(all)
            }
        else:
            raise ValueError('Invalid stream parameters')

        return await self.fetch_text(self.url('p2p/stream/close'),
                                     params=params)

    async def stream_ls(self, headers=False):
        """
        List active P2P streams.
        """
        return await self.fetch_json(self.url('p2p/stream/ls'),
                                     params={'headers': boolarg(headers)})

    listen = listener_open
    dial = stream_dial
    forward = stream_dial
    ls = listener_ls


class BitswapAPI(SubAPI):
    async def ledger(self, peer):
        """
        Show the current ledger for a peer.

        :param str peer: peer id
        """

        return await self.fetch_json(self.url('bitswap/ledger'),
                                     params={ARG_PARAM: peer})

    async def reprovide(self):
        """
        Trigger reprovider.
        """

        return await self.fetch_text(self.url('bitswap/reprovide'))

    async def stat(self):
        """
        Show some diagnostic information on the bitswap agent.
        """

        return await self.fetch_json(self.url('bitswap/stat'))

    async def wantlist(self, peer=None):
        """
        Show blocks currently on the wantlist.

        :param str peer: Specify which peer to show wantlist for
        """

        params = {ARG_PARAM: peer} if peer else {}
        return await self.fetch_json(self.url('bitswap/wantlist'),
                                     params=params)

    async def unwant(self, block):
        """
        Remove a given block from your wantlist.

        :param str block: Key(s) to remove from your wantlist
        """

        return await self.fetch_json(self.url('bitswap/unwant'),
                                     params={ARG_PARAM: block})


class BlockAPI(SubAPI):
    async def get(self, multihash):
        """
        Get a raw IPFS block.

        :param str multihash: The base58 multihash of an existing block to get
        :rtype: :py:class:`bytes`
        """

        return await self.fetch_raw(self.url('block/get'),
                                    params={ARG_PARAM: multihash})

    async def rm(self, multihash, force=False, quiet=False):
        """
        Remove IPFS block(s).

        :param str multihash: The base58 multihash of an existing block to
            remove
        :param bool force: Ignore nonexistent blocks
        :param bool quiet: Write minimal output
        """

        params = {
            ARG_PARAM: multihash,
            'force': boolarg(force),
            'quiet': boolarg(quiet),
        }
        return await self.fetch_json(self.url('block/rm'), params=params)

    async def stat(self, multihash):
        """
        Print information of a raw IPFS block.

        :param str multihash: The base58 multihash of an existing block to stat
        """

        return await self.fetch_json(self.url('block/stat'),
                                     params={ARG_PARAM: multihash})

    async def put(self, filepath, format='v0', mhtype='sha2-256', mhlen=-1):
        """
        Store input as an IPFS block.

        :param str filepath: The path to a file containing the data for the
            block
        :param str format: cid format for blocks
        :param str mhtype: multihash hash function
        :param int mhlen: multihash hash length
        """

        if not os.path.exists(filepath):
            raise Exception('block put: file {0} does not exist'.format(
                filepath))

        params = {
            'format': format,
            'mhtype': mhtype,
            'mhlen': mhlen
        }

        with multi.FormDataWriter() as mpwriter:
            block_payload = payload.BytesIOPayload(open(filepath, 'rb'))
            block_payload.set_content_disposition(
                'form-data', filename=os.path.basename(filepath))
            mpwriter.append_payload(block_payload)

            async with self.driver.session.post(self.url('block/put'),
                                                data=mpwriter,
                                                params=params) as response:
                return await response.json()


class BootstrapAPI(SubAPI):
    """ Bootstrap API """

    async def add(self, peer, default=False):
        params = {
            ARG_PARAM: peer,
            'default': boolarg(default)
        }
        return await self.fetch_json(self.url('bootstrap/add'), params=params)

    async def add_default(self):
        return await self.fetch_json(self.url('bootstrap/add/default'))

    async def list(self):
        """ Shows peers in the bootstrap list """
        return await self.fetch_json(self.url('bootstrap/list'))

    async def rm(self, peer=None, all=False):
        params = {}
        if peer:
            params[ARG_PARAM] = peer
        if all:
            params['all'] = boolarg(all)
        return await self.fetch_json(self.url('bootstrap/rm'), params=params)

    async def rm_all(self):
        """ Removes all peers in the bootstrap list """
        return await self.fetch_json(self.url('bootstrap/rm/all'))


class CidAPI(SubAPI):
    """ CID API """

    async def base32(self, cid):
        return await self.fetch_json(self.url('cid/base32'),
                                     params={ARG_PARAM: cid})

    async def bases(self, prefix=False, numeric=False):
        params = {
            'prefix': boolarg(prefix),
            'numeric': boolarg(numeric)
        }
        return await self.fetch_json(self.url('cid/bases'), params=params)

    async def codecs(self, numeric=False):
        params = {
            'numeric': boolarg(numeric)
        }
        return await self.fetch_json(self.url('cid/codecs'), params=params)

    async def format(self, cid, format=None, version=None, multibase=None):
        """
        Format and convert a CID in various useful ways.

        :param str cid: CID to convert
        :param str format: Printf style format string
        :param int version: CID version to convert to
        :param str multibase: Multibase to display CID in
        """

        params = {
            ARG_PARAM: cid
        }

        if isinstance(version, int):
            params['v'] = str(version)

        if isinstance(format, str):
            params['f'] = format

        if isinstance(multibase, str):
            params['b'] = multibase

        return await self.fetch_json(self.url('cid/format'), params=params)

    async def hashes(self, numeric=False):
        params = {
            'numeric': boolarg(numeric)
        }
        return await self.fetch_json(self.url('cid/hashes'), params=params)


class ConfigAPI(SubAPI):
    """ Configuration management API """

    async def show(self):
        """ Outputs IPFS config file contents """
        return await self.fetch_text(self.url('config/show'))

    async def replace(self, configpath):
        """ Replaces the IPFS configuration with new config file

        :param configpath: new configuration's file path
        :type configpath: :py:class:`str`
        """
        if not os.path.isfile(configpath):
            raise Exception('Config file {} does not exist'.format(configpath))

        with open(configpath, 'rb') as configfd:
            with multi.FormDataWriter() as mpwriter:
                cpay = payload.BytesIOPayload(configfd, filename='config')
                cpay.set_content_disposition('form-data', filename='config')
                mpwriter.append_payload(cpay)

                return await self.post(self.url('config/replace'),
                                       data=mpwriter, outformat='text')

    async def profile_apply(self, profile, dry_run=False):
        """
        Apply profile to config
        """
        params = {
            ARG_PARAM: profile,
            'dry-run': boolarg(dry_run)
        }
        return await self.fetch_json(self.url('config/profile/apply'),
                                     params=params)


class DagAPI(SubAPI):
    async def put(self, filename, format='cbor', input_enc='json',
                  pin=False, offline=False):
        """
        Add a DAG node to IPFS

        :param str filename: a path to the object to import
        :param str format: format to use for the object inside IPFS
        :param str input_enc: object input encoding
        :param bool pin: pin the object after adding (default is False)
        :param bool offline: Offline mode (no announce)
        """

        if not os.path.isfile(filename):
            raise Exception('dag put: {} file does not exist'.format(filename))

        params = {
            'format': format,
            'input-enc': input_enc,
            'pin': boolarg(pin),
            'offline': boolarg(offline)
        }

        basename = os.path.basename(filename)
        with multi.FormDataWriter() as mpwriter:
            dag_payload = payload.BytesIOPayload(open(filename, 'rb'))
            dag_payload.set_content_disposition('form-data',
                                                filename=basename)
            mpwriter.append_payload(dag_payload)

            return await self.post(self.url('dag/put'), mpwriter,
                                   params=params, outformat='json')

    async def get(self, objpath):
        """
        Get a DAG node from IPFS

        :param str objpath: path of the object to fetch
        """

        return await self.fetch_text(self.url('dag/get'),
                                     params={ARG_PARAM: objpath})

    async def resolve(self, path):
        """
        Resolve an IPLD block

        :param str path: path to resolve
        """

        return await self.fetch_json(self.url('dag/resolve'),
                                     params={ARG_PARAM: path})


class DhtAPI(SubAPI):
    async def findpeer(self, peerid, verbose=False):
        return await self.fetch_json(
            self.url('dht/findpeer'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def findprovs(self, key, verbose=False, numproviders=20):
        params = {
            ARG_PARAM: key,
            'verbose': boolarg(verbose),
            'num-providers': numproviders
        }

        async for value in self.mjson_decode(self.url('dht/findprovs'),
                                             params=params):
            yield value

    async def get(self, peerid, verbose=False):
        return await self.fetch_json(
            self.url('dht/get'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def put(self, key, value):
        return await self.fetch_json(self.url('dht/put'),
                                     params=quote_args(key, value))

    async def provide(self, multihash, verbose=False, recursive=False):
        params = {
            ARG_PARAM: multihash,
            'verbose': boolarg(verbose),
            'recursive': boolarg(recursive)
        }

        async for value in self.mjson_decode(
                self.url('dht/provide'), params=params):
            yield value

    async def query(self, peerid, verbose=False):
        async for value in self.mjson_decode(
                self.url('dht/query'),
                params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}):
            yield value


class DiagAPI(SubAPI):
    async def sys(self):
        return await self.fetch_json(self.url('diag/sys'))

    async def cmds_clear(self):
        return await self.fetch_text(self.url('diag/cmds/clear'))


class FilesAPI(SubAPI):
    async def cp(self, source, dest):
        params = quote_args(source, dest)
        return await self.fetch_text(self.url('files/cp'),
                                     params=params)

    async def chcid(self, path, cidversion):
        params = {ARG_PARAM: path, 'cid-version': str(cidversion)}
        return await self.fetch_text(self.url('files/cp'), params=params)

    async def flush(self, path):
        params = {ARG_PARAM: path}
        return await self.fetch_text(self.url('files/flush'),
                                     params=params)

    async def mkdir(self, path, parents=False, cid_version=None):
        params = {ARG_PARAM: path, 'parents': boolarg(parents)}

        if cid_version is not None and isinstance(cid_version, int):
            params['cid-version'] = str(cid_version)

        return await self.fetch_text(self.url('files/mkdir'),
                                     params=params)

    async def mv(self, src, dst):
        params = quote_args(src, dst)
        return await self.fetch_text(self.url('files/mv'),
                                     params=params)

    async def ls(self, path, long=False, unsorted=False):
        params = {
            ARG_PARAM: path,
            'l': boolarg(long),
            'U': boolarg(unsorted)
        }
        return await self.fetch_json(self.url('files/ls'),
                                     params=params)

    async def read(self, path, offset=None, count=None):
        params = {ARG_PARAM: path}

        if offset is not None and isinstance(offset, int):
            params['offset'] = offset
        if count is not None and isinstance(count, int):
            params['count'] = count

        return await self.fetch_raw(self.url('files/read'),
                                    params=params)

    async def rm(self, path, recursive=False, force=False):
        params = {
            ARG_PARAM: path,
            'recursive': boolarg(recursive),
            'force': boolarg(force)
        }
        return await self.fetch_json(self.url('files/rm'),
                                     params=params)

    async def stat(self, path, hash=False, size=False,
                   format=None, with_local=False):
        params = {
            ARG_PARAM: path,
            'hash': boolarg(hash),
            'size': boolarg(size),
            'with-local': boolarg(with_local)
        }

        if isinstance(format, str):
            params['format'] = format

        return await self.fetch_json(self.url('files/stat'),
                                     params=params)

    async def write(self, mfspath, data, create=False,
                    parents=False, cid_version=None,
                    truncate=False, offset=-1, count=-1):
        """
        Write to a mutable file in a given filesystem.

        :param str mfspath: Path to write to
        :param data: Data to write, can be a filepath or bytes data
        :param int offset: Byte offset to begin writing at
        :param bool create: Create the file if it does not exist
        :param bol truncate: Truncate the file to size zero before writing
        :param int count: Maximum number of bytes to read
        :param int cid_version: CID version to use
        """

        params = {
            ARG_PARAM: mfspath,
            'create': boolarg(create),
            'parents': boolarg(parents),
            'truncate': boolarg(truncate)
        }

        if isinstance(offset, int) and offset > 0:
            params['offset'] = offset
        if isinstance(count, int) and count > 0:
            params['count'] = count

        if isinstance(cid_version, int):
            params['cid-version'] = str(cid_version)

        if isinstance(data, bytes):
            file_payload = payload.BytesPayload(data)
            file_payload.set_content_disposition('form-data', name='data',
                                                 filename='data')
        elif isinstance(data, str):
            # Filepath
            file_payload = multi.bytes_payload_from_file(data)
        else:
            raise ValueError('Unknown data format')

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(file_payload)

            return await self.post(self.url('files/write'),
                                   mpwriter, params=params, outformat='text')


class FilestoreAPI(SubAPI):
    async def dups(self):
        return await self.fetch_json(self.url('filestore/dups'))

    def __lsverifyparams(self, cid, fileorder):
        return {
            ARG_PARAM: cid,
            'file-order': boolarg(fileorder)
        }

    async def ls(self, cid, fileorder=False):
        return await self.fetch_json(
            self.url('filestore/ls'),
            params=self.__lsverifyparams(cid, fileorder)
        )

    async def verify(self, cid, fileorder=False):
        return await self.fetch_json(
            self.url('filestore/verify'),
            params=self.__lsverifyparams(cid, fileorder)
        )


class KeyAPI(SubAPI):
    async def list(self, long=False):
        params = {'l': boolarg(long)}
        return await self.fetch_json(self.url('key/list'),
                                     params=params)

    async def gen(self, name, type='rsa', size=2048):
        params = {ARG_PARAM: name, 'type': type, 'size': str(size)}
        return await self.fetch_json(self.url('key/gen'),
                                     params=params)

    async def rm(self, name):
        params = {ARG_PARAM: name}
        return await self.fetch_json(self.url('key/rm'), params=params)

    async def rename(self, src, dst):
        params = quote_args(src, dst)
        return await self.fetch_json(self.url('key/rename'), params=params)


class LogAPI(SubAPI):
    async def tail(self):
        """
        Read the event log.

        async for event in client.log.tail():
            ...
        """

        async for log in self.mjson_decode(self.url('log/tail')):
            yield log

    async def ls(self):
        """ List the logging subsystems """
        return await self.fetch_json(self.url('log/ls'))

    async def level(self, subsystem='all', level='debug'):
        """
        Change logging level

        :param str subsystem: The subsystem logging identifier.
            Use ‘all’ for all subsystems.
        :param str level: The log level, with ‘debug’ the most verbose
            and ‘critical’ the least verbose. One of: debug, info, warning,
            error, critical. Required: yes.
        """

        return await self.fetch_json(self.url('log/level'),
                                     params=quote_args(subsystem, level))


class NamePubsubAPI(SubAPI):
    async def cancel(self, name):
        return await self.fetch_json(self.url('name/pubsub/cancel'),
                                     params={ARG_PARAM: name})

    async def state(self):
        return await self.fetch_json(self.url('name/pubsub/state'))

    async def subs(self):
        return await self.fetch_json(self.url('name/pubsub/subs'))


class NameAPI(SubAPI):
    def __init__(self, driver):
        super().__init__(driver)

        self.pubsub = NamePubsubAPI(driver)

    async def publish(self, path, resolve=True, lifetime='24h',
                      key='self', ttl=None,
                      quieter=False, allow_offline=False):
        params = {
            ARG_PARAM: path,
            'resolve': boolarg(resolve),
            'lifetime': lifetime,
            'key': key,
            'quieter': boolarg(quieter),
            'allow-offline': boolarg(allow_offline)
        }
        if isinstance(ttl, int):
            params['ttl'] = ttl

        return await self.fetch_json(self.url('name/publish'), params=params)

    async def resolve(self, name=None, recursive=False, nocache=False,
                      dht_record_count=None, dht_timeout=None, stream=False):
        params = {
            'recursive': boolarg(recursive),
            'nocache': boolarg(nocache),
            'stream': boolarg(stream)
        }

        if isinstance(dht_record_count, int):
            params['dht-record-count'] = str(dht_record_count)
        if isinstance(dht_timeout, int):
            params['dht-timeout'] = str(dht_timeout)

        if name:
            params[ARG_PARAM] = name

        return await self.fetch_json(self.url('name/resolve'),
                                     params=params)

    async def resolve_stream(self, name=None, recursive=True, nocache=False,
                             dht_record_count=None, dht_timeout=None,
                             stream=True):
        params = {
            'recursive': boolarg(recursive),
            'nocache': boolarg(nocache),
            'stream': boolarg(stream)
        }

        if isinstance(dht_record_count, int):
            params['dht-record-count'] = str(dht_record_count)
        if isinstance(dht_timeout, int):
            params['dht-timeout'] = str(dht_timeout)

        if name:
            params[ARG_PARAM] = name

        async for entry in self.mjson_decode(
                self.url('name/resolve'), params=params):
            yield entry


class ObjectPatchAPI(SubAPI):
    async def add_link(self, cid, name, obj, create=False):
        """
        Add a link to a given object.
        """
        params = {
            ARG_PARAM: [
                cid, name, obj
            ],
        }
        if create is True:
            params['create'] = boolarg(create)

        return await self.fetch_json(self.url('object/patch/add-link'),
                                     params=quote_dict(params))

    async def rm_link(self, cid, name):
        """
        Remove a link from an object.
        """
        return await self.fetch_json(self.url('object/patch/rm-link'),
                                     params=quote_args(cid, name))

    async def append_data(self, cid, filepath):
        """
        Append data to the data segment of a dag node.

        Untested
        """
        params = {
            ARG_PARAM: cid,
        }

        if not os.path.isfile(filepath):
            raise Exception(
                'object append: {} file does not exist'.format(filepath))

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('object/patch/append-data'),
                                   mpwriter, params=params, outformat='json')

    async def set_data(self, cid, filepath):
        """
        Set the data field of an IPFS object.

        Untested
        """
        params = {
            ARG_PARAM: cid,
        }

        if not os.path.isfile(filepath):
            raise Exception(
                'object set_data: {} file does not exist'.format(filepath))

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('object/patch/set-data'),
                                   mpwriter, params=params, outformat='json')


class ObjectAPI(SubAPI):
    def __init__(self, driver):
        super().__init__(driver)
        self.patch = ObjectPatchAPI(driver)

    async def stat(self, objkey):
        params = {ARG_PARAM: objkey}
        return await self.fetch_json(self.url('object/stat'), params=params)

    async def get(self, objkey):
        params = {ARG_PARAM: objkey}
        return await self.fetch_json(self.url('object/get'), params=params)

    async def new(self, template=None):
        params = {}
        return await self.fetch_json(self.url('object/new'), params=params)

    async def links(self, objkey, headers=False):
        params = {
            ARG_PARAM: objkey,
            'headers': boolarg(headers)
        }
        return await self.fetch_json(self.url('object/links'), params=params)

    async def data(self, objkey):
        params = {ARG_PARAM: objkey}
        return await self.fetch_raw(self.url('object/data'), params=params)

    async def put(self, filepath, input_enc='json', datafield_enc='text',
                  pin=None, quiet=True):
        if not os.path.isfile(filepath):
            raise Exception(
                'object put: {} file does not exist'.format(filepath))

        params = {
            'inputenc': input_enc,
            'datafieldenc': datafield_enc,
            'pin': boolarg(pin),
            'quiet': boolarg(quiet)
        }

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('object/put'), mpwriter,
                                   params=params, outformat='json')


class PinAPI(SubAPI):
    async def add(self, multihash, recursive=True, progress=True):
        """
        Pin objects to local storage.
        """

        # We request progress status by default
        params = {
            ARG_PARAM: multihash,
            'recursive': boolarg(recursive),
            'progress': boolarg(progress)
        }

        async for added in self.mjson_decode(
                self.url('pin/add'), params=params):
            yield added

    async def ls(self, multihash=None, pintype='all', quiet=False):
        """
        List objects pinned to local storage.
        """

        params = {
            'type': pintype,
            'quiet': boolarg(quiet)
        }
        if multihash:
            params[ARG_PARAM] = multihash

        return await self.fetch_json(self.url('pin/ls'),
                                     params=params)

    async def rm(self, multihash, recursive=True):
        """
        Remove pinned objects from local storage.
        """

        params = {
            ARG_PARAM: multihash,
            'recursive': boolarg(recursive)
        }
        return await self.fetch_json(self.url('pin/rm'),
                                     params=params)

    async def verify(self, verbose=False, quiet=True):
        """
        Verify that recursive pins are complete.
        """

        params = {
            'verbose': boolarg(verbose),
            'quiet': boolarg(quiet)
        }
        return await self.fetch_json(self.url('pin/verify'),
                                     params=params)

    async def update(self, old, new, unpin=True):
        """
        Update a recursive pin

        :param str old: Path to old object
        :param str new: Path to new object
        :param bool unpin: Remove the old pin
        """

        params = quote_dict({
            ARG_PARAM: [old, new],
            'unpin': boolarg(unpin)
        })
        return await self.fetch_json(self.url('pin/update'), params=params)


class PubSubAPI(SubAPI):
    async def ls(self):
        """
        List the names of the subscribed pubsub topics.
        """
        return await self.fetch_json(self.url('pubsub/ls'))

    async def peers(self):
        """
        List peers communicating over pubsub with this node.
        """
        return await self.fetch_json(self.url('pubsub/peers'))

    async def pub(self, topic, data):
        """
        Publish a message to a given pubsub topic.

        :param str topic: topic to publish the message to
        :param str data: message data
        """

        return await self.post(self.url('pubsub/pub'),
                               None, params=quote_args(topic, data))

    async def sub(self, topic, discover=True):
        """
        Subscribe to messages on a given topic.

        This is an async generator yielding messages as they are read on the
        pubsub topic.

        :param str topic: topic to subscribe to
        :param bool discover: try to discover other peers subscribed to
            the same topic
        """

        params = {ARG_PARAM: topic, 'discover': boolarg(discover),
                  'stream-channels': boolarg(True)}

        async for message in self.mjson_decode(
                self.url('pubsub/sub'),
                method='post',
                headers={'Connection': 'Close'},
                new_session=True,
                timeout=60.0 * 60 * 24 * 8,
                read_timeout=0,
                params=params):
            try:
                converted = self.decode_message(message)
            except Exception:
                print('Could not decode pubsub message ({0})'.format(topic),
                      file=sys.stderr)
            else:
                yield converted

            await asyncio.sleep(0)

    def decode_message(self, psmsg):
        """
        Convert a raw pubsub message (with base64-encoded fields) to a
        readable form
        """

        conv_msg = {}
        conv_msg['from'] = base58.b58encode(
            base64.b64decode(psmsg['from']))
        conv_msg['data'] = base64.b64decode(psmsg['data'])
        conv_msg['seqno'] = base64.b64decode(psmsg['seqno'])
        conv_msg['topicIDs'] = psmsg['topicIDs']
        return conv_msg


class RefsAPI(SubAPI):
    async def local(self):
        async for ref in self.mjson_decode(self.url('refs/local')):
            yield ref


class RepoAPI(SubAPI):
    async def gc(self, quiet=False, streamerrors=False):
        params = {
            'quiet': boolarg(quiet),
            'stream-errors': boolarg(streamerrors)
        }
        return await self.fetch_text(self.url('repo/gc'),
                                     params=params)

    async def verify(self):
        return await self.fetch_json(self.url('repo/verify'))

    async def version(self):
        return await self.fetch_json(self.url('repo/version'))

    async def stat(self, human=False):
        return await self.fetch_json(self.url('repo/stat'),
                                     params={'human': boolarg(human)})


class StatsAPI(SubAPI):
    async def bw(self, peer=None, proto=None, poll=False, interval=None):
        """
        Print ipfs bandwidth information
        """
        params = {
            'poll': boolarg(poll)
        }

        if isinstance(peer, str):
            params['peer'] = peer
        if isinstance(proto, str):
            params['proto'] = proto
        if isinstance(interval, str):
            params['interval'] = interval

        return await self.fetch_json(self.url('stats/bw'), params=params)

    async def bitswap(self):
        return await self.fetch_json(self.url('stats/bitswap'))

    async def repo(self):
        return await self.fetch_json(self.url('stats/repo'))


class SwarmAPI(SubAPI):
    async def peers(self, verbose=True, streams=False, latency=False,
                    direction=False):
        params = {
            'verbose': boolarg(verbose),
            'streams': boolarg(streams),
            'latency': boolarg(latency),
            'direction': boolarg(direction)
        }

        return await self.fetch_json(self.url('swarm/peers'), params=params)

    async def addrs(self):
        return await self.fetch_json(self.url('swarm/addrs'))

    async def addrs_local(self, id=False):
        params = {'id': boolarg(id)}
        return await self.fetch_json(self.url('swarm/addrs/local'),
                                     params=params)

    async def addrs_listen(self):
        return await self.fetch_json(self.url('swarm/addrs/listen'))

    async def connect(self, peer):
        params = {ARG_PARAM: peer}
        return await self.fetch_json(self.url('swarm/connect'),
                                     params=params)

    async def disconnect(self, peer):
        params = {ARG_PARAM: peer}
        return await self.fetch_json(self.url('swarm/disconnect'),
                                     params=params)

    async def filters_add(self, filter):
        params = {ARG_PARAM: filter}
        return await self.fetch_json(self.url('swarm/filters/add'),
                                     params=params)

    async def filters_rm(self, filter):
        params = {ARG_PARAM: filter}
        return await self.fetch_json(self.url('swarm/filters/rm'),
                                     params=params)


class TarAPI(SubAPI):
    async def cat(self, multihash):
        params = {ARG_PARAM: multihash}
        return await self.fetch_raw(self.url('tar/cat'),
                                    params=params)

    async def add(self, tar):
        if not os.path.isfile(tar):
            raise Exception('TAR file does not exist')

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(tar))

            async with self.driver.session.post(self.url('tar/add'),
                                                data=mpwriter) as response:
                return await response.json()


class CoreAPI(SubAPI):
    def _build_add_params(self, **kwargs):
        """
        Used by the different coroutines that post on the 'add' endpoint
        """

        params = {}
        switchlist = [
            'fscache',
            'hidden',
            'nocopy',
            'only_hash',
            'offline',
            'pin',
            'quiet',
            'quieter',
            'raw_leaves',
            'recursive',
            'silent',
            'trickle',
            'dereference_args',
            'wrap_with_directory'
        ]

        for sw, val in kwargs.items():
            if sw in switchlist:
                params[sw.replace('_', '-')] = boolarg(val)

        cid_v = kwargs.pop('cid_version', None)
        if isinstance(cid_v, int):
            params['cid-version'] = str(cid_v)

        chunker = kwargs.pop('chunker', None)
        if isinstance(chunker, str):
            params['chunker'] = chunker

        hashfn = kwargs.pop('hash', None)
        if isinstance(hashfn, str):
            params['hash'] = hashfn

        inline = kwargs.pop('inline', False)
        if inline is True:
            params['inline'] = boolarg(inline)
            params['inline-limit'] = str(kwargs.pop('inline_limit', 32))

        return params

    def _add_post(self, data, params=None):
        return self.driver.session.post(self.url('add'), data=data,
                                        params=params if params else {})

    async def add_single(self, mpart, params=None):
        """
        Add a single-entry multipart (used by add_{bytes,str,json})
        """

        async with self._add_post(
                mpart, params=params if params else {}) as response:
            return await response.json()

    async def add_generic(self, mpart, params=None):
        """
        Add a multiple-entry multipart, and yield the JSON message for every
        entry added. We use mjson_decode with the post method.
        """

        async for added in self.mjson_decode(
                self.url('add'),
                method='post',
                data=mpart,
                params=params if params else {}):
            yield added

    async def add_bytes(self, data, **kwargs):
        """
        Add a file using given bytes as data.

        :param bytes data: file data
        """
        return await self.add_single(multi.multiform_bytes(data),
                                     params=self._build_add_params(**kwargs))

    async def add_str(self, data, name='', codec='utf-8', **kwargs):
        """
        Add a file using given string as data

        :param str data: string data
        :param str codec: input codec, default utf-8
        """
        return await self.add_single(multi.multiform_bytes(
            data.encode(codec), name=name),
            params=self._build_add_params(**kwargs))

    async def add_json(self, data, **kwargs):
        """
        Add a JSON object

        :param str data: json object
        """
        return await self.add_single(multi.multiform_json(data),
                                     params=self._build_add_params(**kwargs))

    async def add(self, *files, **kwargs):
        """
        Add a file or directory to ipfs.

        This is an async generator yielding an IPFS entry for every file added.

        The add_json, add_bytes and add_str coroutines support the same options

        :param files: A list of files/directories to be added to
            the IPFS repository
        :param bool recursive: Add directory paths recursively.
        :param bool quiet: Write minimal output.
        :param bool quieter: Write only final hash.
        :param bool silent: Write no output.
        :param bool progress: Stream progress data.
        :param bool trickle: Use trickle-dag format for dag generation.
        :param bool only_hash: Only chunk and hash - do not write to disk.
        :param bool wrap_with_directory: Wrap files with a directory object.
        :param bool pin: Pin this object when adding. Default: true.
        :param bool raw_leaves: Use raw blocks for leaf nodes.
        :param bool nocopy: Add the file using filestore.
        :param bool fscache: Check the filestore for preexisting blocks.
        :param bool offline: Offline mode (do not announce)
        :param bool hidden: Include files that are hidden. Only takes effect on
            recursive add.
        :param bool inline: Inline small blocks into CIDs
        :param str hash: Hash function to use
        :param int inline_limit: Maximum block size to inline
        :param int cid_version: CID version
        """

        params = self._build_add_params(**kwargs)

        all_files = []
        for fitem in files:
            if isinstance(fitem, list):
                all_files += fitem
            elif isinstance(fitem, str):
                all_files.append(fitem)

        # Build the multipart form and add the files/directories
        with multi.FormDataWriter() as mpwriter:
            for filepath in all_files:
                await asyncio.sleep(0)

                if not isinstance(filepath, str):
                    continue

                if not os.path.exists(filepath):
                    continue

                if os.path.isdir(filepath):
                    dir_listing = multi.DirectoryListing(filepath)
                    names = dir_listing.genNames()
                    for entry in names:
                        await asyncio.sleep(0)
                        _name, _fd, _ctype = entry[1]

                        if _ctype == 'application/x-directory':
                            pay = payload.StringIOPayload(
                                _fd, content_type=_ctype, filename=_name)
                            pay.set_content_disposition('form-data',
                                                        name='file',
                                                        filename=_name)
                            mpwriter.append_payload(pay)
                        else:
                            pay = payload.BufferedReaderPayload(
                                _fd,
                                content_type=_ctype,
                                headers={
                                    'Abspath': _fd.name
                                }
                            )
                            pay.set_content_disposition(
                                'form-data', name='file', filename=_name)
                            mpwriter.append_payload(pay)
                else:
                    basename = os.path.basename(filepath)

                    file_payload = payload.BytesIOPayload(
                        open(filepath, 'rb'),
                        content_type='application/octet-stream',
                        headers={
                            'Abspath': filepath
                        }
                    )

                    file_payload.set_content_disposition('form-data',
                                                         name='file',
                                                         filename=basename)
                    mpwriter.append_payload(file_payload)

            if mpwriter.size == 0:
                raise aioipfs.UnknownAPIError('Multipart is empty')

            async for value in self.add_generic(mpwriter, params=params):
                yield value

    async def commands(self):
        """ List all available commands."""

        return await self.fetch_json(self.url('commands'))

    async def id(self, peer=None):
        """
        Show IPFS node id info.

        :param str peer: peer id to look up, otherwise shows local node info
        """
        params = {ARG_PARAM: peer} if peer else {}
        return await self.fetch_json(self.url('id'), params=params)

    async def cat(self, multihash, offset=None, length=None):
        """
        Show IPFS object data.

        :param str multihash: The base58 multihash of the object to retrieve
        :param int offset: byte offset to begin reading from
        :param int length: maximum number of bytes to read
        """

        params = {ARG_PARAM: multihash}

        if offset is not None and isinstance(offset, int):
            params['offset'] = offset
        if length is not None and isinstance(length, int):
            params['length'] = length

        return await self.fetch_raw(self.url('cat'), params=params)

    async def get(self, multihash, dstdir='.', compress=False,
                  compression_level=-1, archive=True, output=None,
                  progress_callback=None, progress_callback_arg=None,
                  chunk_size=16384):
        """
        Download IPFS objects.

        :param str multihash: The base58 multihash of the object to retrieve
        :param str dstdir: destination directory, current directory by default
        :param bool compress: Compress the output with GZIP compression
        :param str compression_level: The level of compression (1-9)
        :param bool archive: Output a TAR archive
        """

        params = {
            ARG_PARAM: multihash,
            'compress': boolarg(compress),
            'compression-level': str(compression_level),
            'archive': boolarg(archive)
        }

        if isinstance(output, str):
            params['output'] = output

        archive_path = tempfile.mkstemp(prefix='aioipfs')[1]

        # We read chunk by chunk the tar data coming from the
        # daemon and use aiofiles to asynchronously write the data to
        # the temporary file

        read_so_far = 0
        async with aiofiles.open(archive_path, 'wb') as fd:
            async with self.driver.session.get(self.url('get'),
                                               params=params) as response:
                if response.status != 200:
                    raise aioipfs.APIError(http_status=response.status)

                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break

                    read_so_far += len(chunk)

                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(multihash, read_so_far,
                                                progress_callback_arg)

                    await fd.write(chunk)
                    await asyncio.sleep(0)

                await response.release()

        def extract():
            # Synchronous tar extraction runs in the executor
            mode = 'r|gz' if compress is True else 'r|'
            try:
                with tarfile.open(name=archive_path, mode=mode) as tf:
                    tf.extractall(path=dstdir)
                os.unlink(archive_path)
            except Exception as e:
                print('Could not extract TAR file:', str(e), file=sys.stderr)
                os.unlink(archive_path)
                return False

            return True

        # Run the tar extraction inside asyncio's threadpool
        loop = asyncio.get_event_loop()
        tar_future = loop.run_in_executor(None, extract)
        return await tar_future

    async def ls(self, path, headers=False, resolve_type=True):
        """
        List directory contents for Unix filesystem objects.

        :param str path: The path to the IPFS object(s) to list links from
        :param bool headers: Print table headers (Hash, Size, Name)
        :param bool resolve_type: Resolve linked objects to get their types
        """

        params = {
            'resolve-type': boolarg(resolve_type),
            'headers': boolarg(headers),
            ARG_PARAM: path
        }
        return await self.fetch_json(self.url('ls'), params=params)

    async def mount(self, ipfspath, ipnspath):
        params = {
            'ipfs-path': ipfspath,
            'ipns-path': ipnspath,
        }
        return await self.fetch_json(self.url('mount'), params=params)

    async def ping(self, peerid, count=5):
        """
        Send echo request packets to IPFS hosts.

        :param str peerid: ID of peer to be pinged
        :param int count: Number of ping messages to send
        """

        async for value in self.mjson_decode(
                self.url('ping'),
                params={ARG_PARAM: peerid, 'count': str(count)}):
            yield value

    async def shutdown(self):
        """ Shut down the ipfs daemon """
        return await self.fetch_text(self.url('shutdown'))

    async def version(self, number=True, commit=True, repo=True,
                      all=True):
        """
        Show ipfs version information
        """
        params = {
            'number': boolarg(number),
            'commit': boolarg(commit),
            'repo': boolarg(repo),
            'all': boolarg(all)
        }

        return await self.fetch_json(self.url('version'), params=params)

    async def dns(self, name, recursive=False):
        """
        Resolve DNS links

        :param str name: domain name to resolve
        :param bool recursive: Resolve until the result is not a DNS link.
        """
        params = {
            ARG_PARAM: name,
            'recursive': boolarg(recursive)
        }
        return await self.fetch_json(self.url('dns'), params=params)

    async def resolve(self, name, recursive=False,
                      dht_record_count=None, dht_timeout=None):
        """
        Resolve the value of names to IPFS
        """

        params = {
            ARG_PARAM: name,
            'recursive': boolarg(recursive),
        }

        if isinstance(dht_record_count, int):
            params['dht-record-count'] = str(dht_record_count)

        if isinstance(dht_timeout, int):
            params['dht-timeout'] = str(dht_timeout)

        return await self.fetch_json(self.url('resolve'), params=params)
