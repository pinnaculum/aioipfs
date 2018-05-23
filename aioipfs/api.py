
import base58, base64
import json
import os.path
import tarfile
import tempfile
import sys

import asyncio
import async_timeout
import aiohttp
import aiofiles
import aioipfs

from aiohttp import payload, multipart, web_exceptions
from aiohttp.web_exceptions import (HTTPOk,
        HTTPPartialContent, HTTPError,
        HTTPSuccessful, HTTPInternalServerError,
        HTTPServerError)

from yarl import URL, quoting
from async_generator import async_generator, yield_, yield_from_

from . import multi

# Convenient functions

ARG_PARAM = 'arg'

def boolarg(arg):
    return str(arg).lower()

def quote_args(*args):
    # Used in the few cases where there are multiple 'arg=' URL params
    # that yarl can't handle at the moment
    quoter = quoting._Quoter()
    quoted = ''

    if len(args) >  0:
        for arg in args:
            quoted += '&{0}={1}'.format(ARG_PARAM, quoter(str(arg)))
        return quoted[1:]

def decode_json(data):
    if not data:
        return None
    try:
        json_obj = json.loads(data.decode())
    except Exception as exc:
        print('Could not read JSON object:', str(exc), file=sys.stderr)
        return None

    return json_obj

HTTP_ERROR_CODES = [
    HTTPInternalServerError.status_code,
    HTTPServerError.status_code
]

DEFAULT_TIMEOUT = 60 * 60

class SubAPI(object):
    """ Master class for all classes implementing API functions """

    def __init__(self, driver):
        self.driver = driver

    def url(self, path):
        return self.driver.api_endpoint(path)

    def decode_error(self, errormsg):
        try:
            decoded_json = json.loads(errormsg)
            msg  = decoded_json['Message']
            code = decoded_json['Code']
            return msg, code
        except Exception as e:
            return None, None

    async def fetch_text(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, textdata = response.status, await response.text()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(textdata)
                raise aioipfs.APIException(code=code, message=msg)
            return textdata

    async def fetch_raw(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, data = response.status, await response.read()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(data)
                raise aioipfs.APIException(code=code, message=msg)
            return status, data

    async def fetch_json(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.get(url, params=params) as response:
            status, jsondata = response.status, await response.json()
            if status in HTTP_ERROR_CODES:
                if 'Message' in jsondata and 'Code' in jsondata:
                    raise aioipfs.APIException(code=jsondata['Code'],
                            message=jsondata['Message'])
                else:
                    raise aioipfs.APIUnknownException()

            return jsondata

    async def post(self, url, data, headers={}, params={},
            timeout=DEFAULT_TIMEOUT, outformat='text'):
        async with self.driver.session.post(url, data=data,
                headers=headers, params=params) as response:
            if response.status in HTTP_ERROR_CODES:
                raise aioipfs.APIException(httpstatus=status)

            if outformat == 'text':
                return await response.text()
            elif outformat == 'json':
                return await response.json()
            else:
                raise Exception('Unknown output format {0}'.format(outformat))

class P2PAPI(SubAPI):
    # /p2p/*

    async def listener_open(self, name, address):
        params = quote_args(name, address)
        return await self.fetch_json(self.url('p2p/listener/open'),
                params=params)

    async def listener_ls(self):
        return await self.fetch_json(self.url('p2p/listener/ls'))

    async def stream_dial(self, peer, protocol, address):
        params = quote_args(peer, protocol, address)
        return await self.fetch_json(self.url('p2p/stream/dial'),
                params=params)

    async def stream_close(self, streamid, all=False):
        return await self.fetch_text(self.url('p2p/stream/close'),
                params={ARG_PARAM: streamid})

class BitswapAPI(SubAPI):
    async def ledger(self, peer):
        return await self.fetch_json(self.url('bitswap/ledger'),
            params={ARG_PARAM: peer})

    async def reprovide(self):
        return await self.fetch_text(self.url('bitswap/reprovide'))

    async def stat(self):
        return await self.fetch_json(self.url('bitswap/stat'))

    async def wantlist(self, peer=None):
        params={ARG_PARAM: peer} if peer else {}
        return await self.fetch_json(self.url('bitswap/wantlist'),
            params=params)

    async def unwant(self, block):
        return await self.fetch_json(self.url('bitswap/unwant'),
            params={ARG_PARAM: block})

class BlockAPI(SubAPI):
    ## /block/*

    async def get(self, multihash):
        return await self.fetch_text(self.url('block/get'),
            params={ARG_PARAM: multihash})

    async def rm(self, multihash, force=False):
        params = {
            ARG_PARAM: multihash,
            'force': boolarg(force)
        }
        return await self.fetch_json(self.url('block/rm'),
            params=params)

    async def stat(self, multihash):
        return await self.fetch_json(self.url('block/stat'),
            params={ARG_PARAM: multihash})

    async def put(self, file, format='v0', mhtype='sha2-256', mhlen=-1):
        if not os.path.exists(file):
            raise Exception('block put: file {0} does not exist'.format(
                file))

        params = {
                'format': format,
                'mhtype': mhtype,
                'mhlen': mhlen
                }

        with multi.FormDataWriter() as mpwriter:
            block_payload = payload.BytesIOPayload(open(file, 'rb'))
            block_payload.set_content_disposition('form-data',
                    filename=os.path.basename(file))
            mpwriter.append_payload(block_payload)

            async with self.driver.session.post(self.url('block/put'),
                    data=mpwriter) as response:
                return await response.json()

class BootstrapAPI(SubAPI):
    """ Bootstrap API """

    async def add(self, peer, default=False):
        params = {
            ARG_PARAM: peer,
            'default': boolarg(default)
        }
        return await self.fetch_json(self.url('bootstrap/add'), params=params)

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

    async def rmall(self):
        """ Removes all peers in the bootstrap list """
        return await self.fetch_json(self.url('bootstrap/rm/all'))

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

                return await self.post(self.url('config/replace'), data=mpwriter,
                    outformat='text')

class DagAPI(SubAPI):
    # /dag/*

    async def put(self, filename):
        if not os.path.isfile(filename):
            raise Exception('dag put: {} file does not exist'.format(filename))

        basename = os.path.basename(filename)
        with multi.FormDataWriter() as mpwriter:
            dag_payload = payload.BytesIOPayload(open(filename, 'rb'))
            dag_payload.set_content_disposition('form-data',
                    filename=basename)
            mpwriter.append_payload(dag_payload)

            return await self.post(self.url('dag/put'), mpwriter,
                    outformat='json')

    async def get(self, multihash):
        return await self.fetch_text(self.url('dag/get'),
                params={ARG_PARAM: multihash})

    async def resolve(self, multihash):
        return await self.fetch_text(self.url('dag/resolve'),
                params={ARG_PARAM: multihash})

class DhtAPI(SubAPI):
    # /dht/*

    async def findpeer(self, peerid, verbose=False):
        return await self.fetch_json(self.url('dht/findpeer'),
                params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)})

    async def findprovs(self, peerid, verbose=False, numproviders=20):
        params={
                ARG_PARAM: peerid,
                'verbose': boolarg(verbose),
                'num-providers': numproviders
                }

        return await self.fetch_json(self.url('dht/findprovs'),
                params=params)

    async def get(self, peerid, verbose=False):
        return await self.fetch_json(self.url('dht/get'),
                params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)})

    async def provide(self, multihash, verbose=False, recursive=False):
        params={
                ARG_PARAM: peerid,
                'verbose': boolarg(verbose),
                'recursive': boolarg(recursive)
                }

        return await self.fetch_json(self.url('dht/provide'),
                params={ARG_PARAM: multihash, 'verbose': boolarg(verbose)})

    async def query(self, peerid, verbose=False):
        return await self.fetch_json(self.url('dht/query'),
                params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)})

class FilesAPI(SubAPI):
    # /files/*
    # TODO: implement /files/write

    async def cp(self, source, dest):
        params = quote_args(source, dest)
        return await self.fetch_text(self.url('files/cp'),
                params=params)

    async def flush(self, path):
        params = {ARG_PARAM: path}
        return await self.fetch_text(self.url('files/flush'),
                params=params)

    async def mkdir(self, path, parents=False):
        params = {ARG_PARAM: path, 'parents': boolarg(parents)}
        return await self.fetch_text(self.url('files/mkdir'),
                params=params)

    async def mv(self, src, dst):
        params = quote_args(src, dst)
        return await self.fetch_text(self.url('files/mv'),
                params=params)

    async def ls(self, path, long=False):
        params = {ARG_PARAM: path, 'l': boolarg(long)}
        return await self.fetch_json(self.url('files/ls'),
                params=params)

    async def rm(self, path, recursive=False):
        params = {ARG_PARAM: path, 'recursive': boolarg(recursive)}
        return await self.fetch_json(self.url('files/rm'),
                params=params)

    async def stat(self, path, hash=False, size=False):
        params = {
                ARG_PARAM: path,
                'hash': boolarg(hash),
                'size': boolarg(size)
        }
        return await self.fetch_json(self.url('files/stat'),
                params=params)

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

class LogAPI(SubAPI):
    # /log/*
    @async_generator
    async def tail(self):
        async with self.driver.session.get(
                self.url('log/tail')) as response:
            async for raw_message in response.content:
                log_message = decode_json(raw_message)
                if log_message:
                    await yield_(log_message)

    async def ls(self):
        return await self.fetch_json(self.url('log/ls'))

class NameAPI(SubAPI):
    async def publish(self, path, resolve=True, lifetime='24h', key='self'):
        params = {
                ARG_PARAM: path,
                'resolve': boolarg(resolve),
                'lifetime': lifetime,
                'key': key
        }
        return await self.fetch_json(self.url('name/publish'), params=params)

    async def resolve(self, name=None, recursive=False, nocache=False):
        params = {
                'recursive': boolarg(recursive),
                'nocache': boolarg(nocache)
        }

        if name:
            params[ARG_PARAM] = name

        return await self.fetch_json(self.url('name/resolve'),
                params=params)

class ObjectAPI(SubAPI):
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

class PinAPI(SubAPI):
    # /pin/*

    @async_generator
    async def add(self, multihash, recursive=True):
        # We request progress status by default
        params = {
                ARG_PARAM: multihash,
                'recursive': boolarg(recursive),
                'progress': boolarg(True)
            }

        async with self.driver.session.get(self.url('pin/add'),
                params=params) as response:
            async for raw_message in response.content:
                added = decode_json(raw_message)
                if added:
                    await yield_(added)

    async def ls(self, multihash=None, pintype='all', quiet=False):
        params = {
                'type': pintype,
                'quiet': boolarg(quiet)
                }
        if multihash:
            params[ARG_PARAM] = multihash

        return await self.fetch_json(self.url('pin/ls'),
            params=params)

    async def rm(self, multihash, recursive=True):
        params = {
                ARG_PARAM: multihash,
                'recursive': boolarg(recursive)
                }
        return await self.fetch_json(self.url('pin/rm'),
            params=params)

    async def verify(self, verbose=False, quiet=True):
        params = {
                'verbose': boolarg(verbose),
                'quiet': boolarg(quiet)
                }
        return await self.fetch_json(self.url('pin/verify'),
            params=params)

class PubSubAPI(SubAPI):
    # /pubsub/*

    async def ls(self):
        return await self.fetch_json(self.url('pubsub/ls'))

    async def peers(self):
        return await self.fetch_json(self.url('pubsub/peers'))

    async def pub(self, topic, data):
        # Manually encode with YARL's quoter since it cannot handle this
        # case i believe (two arguments with same key name)
        params = quote_args(topic, data)
        return await self.fetch_text(self.url('pubsub/pub'),
                params=params)

    @async_generator
    async def sub(self, topic, discover=True):
        def convert_message(pubsubm):
            msg = {}
            msg['from'] = base58.b58encode(
                base64.b64decode(pubsubm['from']))
            msg['data'] = base64.b64decode(pubsubm['data'])
            msg['seqno'] = base64.b64decode(pubsubm['seqno'])
            msg['topicIDs'] = pubsubm['topicIDs']
            return msg

        args = { ARG_PARAM: topic, 'discover': boolarg(discover) }

        async with self.driver.session.get(self.url('pubsub/sub'),
                params=args) as response:
            async for line in response.content:
                await asyncio.sleep(0)
                message = decode_json(line)
                if not message:
                    continue

                if 'from' not in message or 'data' not in message:
                    continue

                await yield_(convert_message(message))
            await response.release()

class RefsAPI(SubAPI):
    # /refs/*

    @async_generator
    async def local(self):
        async with self.driver.session.get(
                self.url('refs/local')) as response:
            async for entry in response.content:
                ref = decode_json(entry)
                if ref:
                    await yield_(ref)

class RepoAPI(SubAPI):
    # /repo/*
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

class SwarmAPI(SubAPI):
    # /swarm/*
    async def peers(self):
        return await self.fetch_json(self.url('swarm/peers'))

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

class TarAPI(SubAPI):
    # /tar/*
    async def cat(self, multihash):
        params = { ARG_PARAM: multihash }
        status, data = await self.fetch_raw(self.url('tar/cat'),
                params=params)
        return data

    async def add(self, tar):
        if not os.path.exists(tar):
            raise Exception('Tar file does not exist')
        basename = os.path.basename(tar)
        with multi.FormDataWriter() as mpwriter:
            tar_payload = payload.BytesIOPayload(open(tar, 'rb'))
            tar_payload.set_content_disposition('form-data', filename =
                    basename, name=basename)
            mpwriter.append_payload(tar_payload)

            async with self.driver.session.post(self.url('tar/add'),
                    data=mpwriter) as response:
                return await response.json()

class StatsAPI(SubAPI):
    # /stats/*
    async def bw(self):
        return await self.fetch_json(self.url('stats/bw'))

    async def bitswap(self):
        return await self.fetch_json(self.url('stats/bitswap'))

    async def repo(self):
        return await self.fetch_json(self.url('stats/repo'))

class CoreAPI(SubAPI):
    def poster(self, data, params={}):
        return self.driver.session.post(self.url('add'), data=data,
            params=params)

    @async_generator
    async def add_generic(self, mpart, params={}):
        async with self.driver.session.post(self.url('add'),
                data=mpart, params=params) as response:
            async for message in response.content:
                added = decode_json(message)
                if added:
                    await yield_(added)

    @async_generator
    async def add_bytes(self, bytes, *args, **kwargs):
        async for value in self.add_generic(multi.multiform_bytes(bytes)):
            await yield_(value)

    @async_generator
    async def add_json(self, json, *args, **kwargs):
        async for value in self.add_generic(multi.multiform_json(json)):
            await yield_(value)

    @async_generator
    async def add(self, files, callback=None, *args, **kwargs):
        params = {
            'trickle': boolarg(kwargs.pop('trickle', False)),
            'only-hash': boolarg(kwargs.pop('only_hash', False)),
            'wrap-with-directory': boolarg(kwargs.pop('wrap_with_directory', False)),
            'pin': boolarg(kwargs.pop('pin', True)),
            'hidden': boolarg(kwargs.pop('hidden', False)),
            'quiet': boolarg(kwargs.pop('quiet', False)),
            'quieter': boolarg(kwargs.pop('quieter', False)),
            'silent': boolarg(kwargs.pop('silent', False)),
            'raw-leaves': boolarg(kwargs.pop('raw_leaves', False)),
            'nocopy': boolarg(kwargs.pop('nocopy', False)),
            'recursive': boolarg(kwargs.pop('recursive', False))
        }

        if type(files) == str:
            files = [files]

        # Build the multipart form and add the files/directories
        with multi.FormDataWriter() as mpwriter:
            for filepath in files:
                await asyncio.sleep(0)
                if not os.path.exists(filepath):
                    continue
                if os.path.isdir(filepath):
                    dir_listing = multi.DirectoryListing(filepath)
                    names = dir_listing.genNames()
                    for entry in names:
                        await asyncio.sleep(0)
                        _name, _fd, _ctype = entry[1]
                        if _ctype == 'application/x-directory':
                            pay = payload.StringIOPayload(_fd,
                                    content_type=_ctype, filename=_name)
                            pay.set_content_disposition('file', name=_name,
                                    filename=_name)
                            mpwriter.append_payload(pay)
                        else:
                            pay = payload.BufferedReaderPayload(_fd, filename=_name)
                            pay.set_content_disposition('file',
                                    filename=_name, name=_name)
                            mpwriter.append_payload(pay)
                else:
                    basename = os.path.basename(filepath)

                    file_payload = payload.BytesIOPayload(open(filepath, 'rb'))
                    file_payload.set_content_disposition('file', name=basename,
                            filename=basename)
                    mpwriter.append_payload(file_payload)

            async for value in self.add_generic(mpwriter, params=params):
                await yield_(value)

    # /commands
    async def commands(self):
        return await self.fetch_json(self.url('commands'))

    # /id
    async def id(self):
        return await self.fetch_json(self.url('id'))

    # /cat
    async def cat(self, multihash):
        params = { ARG_PARAM: multihash }
        status, data = await self.fetch_raw(self.url('cat'),
                params=params)
        return data

    # /get
    async def get(self, multihash, dstdir='.', *args, **kwargs):
        opts = {
                'compress': boolarg(kwargs.pop('compress', False)),
                'compression-level': str(kwargs.pop('compression_level', -1)),
                'archive': boolarg(True),
                ARG_PARAM: multihash
                }
        progress_callback = kwargs.pop('progress_callback', None)
        progress_callback_arg = kwargs.pop('progress_callback_arg', None)
        default_chunk_size = 4096
        chunk_size = kwargs.pop('chunk_size', default_chunk_size)

        archive_path = tempfile.mkstemp(prefix='aioipfs')[1]

        # We read chunk by chunk the tar data coming from the
        # daemon and use aiofiles to asynchronously write the data to
        # the temporary file

        read_so_far = 0
        async with aiofiles.open(archive_path, 'wb') as fd:
            async with self.driver.session.get(self.url('get'),
                    params=opts) as response:
                content_length = response.headers.get("X-Content-Length", 0)

                if response.status != 200:
                    return False

                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break

                    chunk_size = len(chunk)
                    read_so_far += chunk_size

                    if callable(progress_callback):
                        await progress_callback(multihash, read_so_far,
                                progress_callback_arg)

                    await fd.write(chunk)
                    await asyncio.sleep(0)

                await response.release()

        def extract():
            # Synchronous tar extraction runs in the executor
            mode = 'r|gz' if opts['compress'] == 'True' else 'r|'
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
        return await self.fetch_text(self.url('ping'),
            params={ARG_PARAM: peerid, 'count': str(count)})

    # /shutdown
    async def shutdown(self):
        return await self.fetch_text(self.url('shutdown'))

    # /version
    async def version(self):
        return await self.fetch_json(self.url('version'))
