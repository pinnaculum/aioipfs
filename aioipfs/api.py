import os.path
import tarfile
import tempfile
import sys
from pathlib import Path

import asyncio
import aiofiles
import aioipfs

from aiohttp import payload

from .apis import SubAPI
from . import multi
from .helpers import *  # noqa


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

    async def stat(self, verbose=False, human=False):
        """
        Show some diagnostic information on the bitswap agent.
        """

        params = {
            'verbose': boolarg(verbose),
            'human': boolarg(human)
        }

        return await self.fetch_json(self.url('bitswap/stat'),
                                     params=params)

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

        (this command has been deprecated it seems).

        :param str block: Key(s) to remove from your wantlist
        """

        return await self.fetch_json(self.url('bitswap/unwant'),
                                     params={ARG_PARAM: block})


class BlockAPI(SubAPI):
    async def get(self, cid):
        """
        Get a raw IPFS block.

        :param str cid: The cid of an existing block to get
        :rtype: :py:class:`bytes`
        """

        return await self.fetch_raw(self.url('block/get'),
                                    params={ARG_PARAM: cid})

    async def rm(self, cid, force=False, quiet=False):
        """
        Remove IPFS block(s).

        :param str cid: The cid of an existing block to remove
        :param bool force: Ignore nonexistent blocks
        :param bool quiet: Write minimal output
        """

        params = {
            ARG_PARAM: cid,
            'force': boolarg(force),
            'quiet': boolarg(quiet),
        }
        return await self.fetch_json(self.url('block/rm'), params=params)

    async def stat(self, cid):
        """
        Print information of a raw IPFS block.

        :param str cid: The cid of an existing block to stat
        """

        return await self.fetch_json(self.url('block/stat'),
                                     params={ARG_PARAM: cid})

    async def put(self, filepath, cid_codec=None,
                  format='v0', mhtype='sha2-256', mhlen=-1,
                  allow_big_block=False, pin=True):
        """
        Store input as an IPFS block.

        :param str cid_codec: Multicodec to use in returned CID
        :param bool allow_big_block: Disable block size check and allow
            creation of blocks bigger than 1MiB
        :param str filepath: The path to a file containing the data for the
            block
        :param str mhtype: multihash hash function
        :param int mhlen: multihash hash length
        :param bool pin: pin block
        """

        if not os.path.exists(filepath):
            raise Exception('block put: file {0} does not exist'.format(
                filepath))

        params = {
            'mhtype': mhtype,
            'mhlen': mhlen,
            'pin': boolarg(pin),
            'allow-big-block': boolarg(allow_big_block)
        }

        if isinstance(cid_codec, str):
            params['cid-codec'] = cid_codec

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

    async def add(self, peer):
        return await self.fetch_json(
            self.url('bootstrap/add'),
            params={ARG_PARAM: peer}
        )

    async def add_default(self):
        return await self.fetch_json(self.url('bootstrap/add/default'))

    async def list(self):
        """ Shows peers in the bootstrap list """
        return await self.fetch_json(self.url('bootstrap/list'))

    async def rm(self, peer: str):
        return await self.fetch_json(
            self.url('bootstrap/rm'),
            params={ARG_PARAM: peer}
        )

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

    async def codecs(self, numeric=False, supported=False):
        params = {
            'numeric': boolarg(numeric),
            'supported': boolarg(supported)
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

    async def hashes(self, numeric=False, supported=False):
        params = {
            'numeric': boolarg(numeric),
            'supported': boolarg(supported)
        }
        return await self.fetch_json(self.url('cid/hashes'), params=params)


class ConfigAPI(SubAPI):
    """ Configuration management API """

    async def config(self,
                     key: str,
                     value=None,
                     boolean: bool = False,
                     json: bool = False):
        """
        Get or set IPFS config values

        :param str key: The key of the config entry (e.g. "Addresses.API")
        :param str value: The value to set the config entry to
        :param bool boolean: Set a boolean value
        :param bool json: Parse stringified JSON
        """

        params = {}

        if value is not None:
            if boolean:
                params[ARG_PARAM] = [key, boolarg(value)]
            else:
                params[ARG_PARAM] = [key, value]
        else:
            params = {ARG_PARAM: key}

        params['bool'] = boolarg(boolean)
        params['json'] = boolarg(json)

        return await self.fetch_json(
            self.url('config'),
            params=params
        )

    async def show(self):
        """ Outputs IPFS config file contents """
        return await self.fetch_json(self.url('config/show'))

    async def replace(self, configpath):
        """
        Replaces the IPFS configuration with new config file

        :param str configpath: new configuration's file path
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

        :param str profile: The profile to apply to the config
        :param bool dry_run: print difference between the current config
            and the config that would be generated
        """
        params = {
            ARG_PARAM: profile,
            'dry-run': boolarg(dry_run)
        }
        return await self.fetch_json(self.url('config/profile/apply'),
                                     params=params)


class DhtAPI(SubAPI):
    async def findpeer(self, peerid, verbose=False):
        """
        DEPRECATED: This command is deprecated
        """
        return await self.fetch_json(
            self.url('dht/findpeer'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def findprovs(self, key, verbose=False, numproviders=20):
        """
        DEPRECATED: This command is deprecated
        """
        params = {
            ARG_PARAM: key,
            'verbose': boolarg(verbose),
            'num-providers': numproviders
        }

        async for value in self.mjson_decode(self.url('dht/findprovs'),
                                             params=params):
            yield value

    async def get(self, peerid, verbose=False):
        """
        DEPRECATED: This command is deprecated
        """
        return await self.fetch_json(
            self.url('dht/get'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def put(self, key, value):
        """
        DEPRECATED: This command is deprecated
        """
        return await self.fetch_json(self.url('dht/put'),
                                     params=quote_args(key, value))

    async def provide(self, cid, verbose=False, recursive=False):
        """
        DEPRECATED: This command is deprecated
        """
        params = {
            ARG_PARAM: cid,
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

    async def cmds(self, verbose=False):
        """
        List commands run on this IPFS node.
        """
        return await self.fetch_json(self.url('diag/cmds'),
                                     params={'verbose': boolarg(verbose)})

    async def cmds_set_time(self, time: str):
        """
        Set how long to keep inactive requests in the log.
        """
        return await self.fetch_text(self.url('diag/cmds/set-time'),
                                     params={ARG_PARAM: time})

    async def cmds_clear(self):
        return await self.fetch_text(self.url('diag/cmds/clear'))

    async def profile(self,
                      output: str = None,
                      collectors: list = None,
                      profile_time: str = None,
                      mutex_profile_fraction: int = None,
                      block_profile_rate: str = None):
        """
        Collect a performance profile for debugging.

        TODO: support passing collectors as an array
        """

        params = {}

        if isinstance(output, str):
            params['output'] = output

        if isinstance(profile_time, str):
            params['profile-time'] = profile_time

        if isinstance(mutex_profile_fraction, int):
            params['mutex-profile-fraction'] = mutex_profile_fraction

        if isinstance(block_profile_rate, str):
            params['block-profile-rate'] = block_profile_rate

        return await self.fetch_text(self.url('diag/profile'),
                                     params=params)


class FileAPI(SubAPI):
    async def ls(self, path):
        params = {ARG_PARAM: path}
        return await self.fetch_json(self.url('file/ls'), params=params)


class FilesAPI(SubAPI):
    async def cp(self, source, dest, parents: bool = False):
        """
        Add references to IPFS files and directories in MFS
        (or copy within MFS).
        """

        params = quote_dict({
            ARG_PARAM: [source, dest],
            'parents': boolarg(parents)
        })

        return await self.fetch_text(self.url('files/cp'),
                                     params=params)

    async def chcid(self, path: str,
                    cidversion: int,
                    hashfn: str = None):
        params = {ARG_PARAM: path, 'cid-version': str(cidversion)}

        if isinstance(hashfn, str):
            params['hash'] = hashfn

        return await self.fetch_text(self.url('files/chcid'), params=params)

    async def flush(self, path: str = '/'):
        """
        Flush a given path's data to disk.
        """
        params = {ARG_PARAM: path}
        return await self.fetch_text(self.url('files/flush'),
                                     params=params)

    async def mkdir(self, path, parents=False, cid_version=None,
                    hashfn: str = None):
        params = {ARG_PARAM: path, 'parents': boolarg(parents)}

        if isinstance(hashfn, str):
            params['hash'] = hashfn

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

    async def read(self, path,
                   offset: int = None,
                   count: int = None):
        params = {ARG_PARAM: path}

        if offset is not None and isinstance(offset, int):
            params['offset'] = offset
        if count is not None and isinstance(count, int):
            params['count'] = count

        return await self.fetch_raw(self.url('files/read'),
                                    params=params)

    async def rm(self, path,
                 recursive: bool = False, force: bool = False):
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
                    raw_leaves=False,
                    hashfn: str = None,
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
        :param str hashfn: Hash function to use. Will set Cid
            version to 1 if used. (experimental).
        """

        params = {
            ARG_PARAM: mfspath,
            'create': boolarg(create),
            'parents': boolarg(parents),
            'raw-leaves': boolarg(raw_leaves),
            'truncate': boolarg(truncate)
        }

        if isinstance(offset, int) and offset > 0:
            params['offset'] = offset
        if isinstance(count, int) and count > 0:
            params['count'] = count

        if isinstance(cid_version, int):
            params['cid-version'] = str(cid_version)

        if isinstance(hashfn, str):
            params['hash'] = hashfn

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
    async def key_import(self,
                         keypath: str,
                         name,
                         ipns_base: str = None,
                         format='libp2p-protobuf-cleartext',
                         allow_any_keytype: bool = False):
        """
        Import a key and prints imported key id

        :param str keypath: filepath of the key to import
        :param str name: name to associate with key in keychain
        :param str ipns_base: Encoding used for keys: Can either be a
            multibase encoded CID or a base58btc encoded multihash
        :param str format: The format of the private key to import,
            libp2p-protobuf-cleartext or pem-pkcs8-cleartext
        :param bool allow_any_keytype: Allow importing any key type
        """

        params = {
            ARG_PARAM: name,
            'format': format,
            'allow-any-key-type': boolarg(allow_any_keytype)
        }

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(keypath))

            return await self.post(self.url('key/import'),
                                   mpwriter, params=params,
                                   outformat='json')

    async def export(self, name, output=None,
                     format='libp2p-protobuf-cleartext'):
        """
        Export a keypair

        :param str name: name of the key to export
        :param str output: The path where the output should be stored
        :param str format: The format of the private key to import,
            libp2p-protobuf-cleartext or pem-pkcs8-cleartext
        """

        params = {
            ARG_PARAM: name,
            'format': format
        }

        if output:
            params['output'] = str(output)

        return await self.fetch_json(self.url('key/export'),
                                     params=params)

    async def list(self, long=False,
                   ipns_base: str = None):
        params = {'l': boolarg(long)}

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        return await self.fetch_json(self.url('key/list'),
                                     params=params)

    async def gen(self, name, type='rsa', size: int = 2048,
                  ipns_base: str = None):
        params = {ARG_PARAM: name, 'type': type, 'size': str(size)}

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        return await self.fetch_json(self.url('key/gen'),
                                     params=params)

    async def rm(self, name,
                 ipns_base: str = None):
        params = {ARG_PARAM: name}

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        return await self.fetch_json(self.url('key/rm'), params=params)

    async def rename(self, src, dst, ipns_base=None, force: bool = False):
        params = {
            ARG_PARAM: [src, dst],
            'force': boolarg(force)
        }

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        return await self.fetch_json(self.url('key/rename'),
                                     params=quote_dict(params))

    async def rotate(self, old_key=None, key_type=None, size=None):
        params = {}
        if old_key:
            params['old_key'] = old_key
        if key_type:
            params['type'] = key_type
        if size:
            params['size'] = size

        return await self.fetch_text(self.url('key/rotate'), params=params)


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
                      quieter=False, allow_offline=False,
                      ipns_base: str = None):
        """
        Publish IPNS names

        :param str path: ipfs path of the object to be published
        :param bool resolve: Check if the given path can be resolved
            before publishing
        :param str lifetime: Time duration that the record will be
            valid for.  This accepts durations such as "300s", "1.5h"
            or "2h45m". Valid time units are "ns", "us" (or "µs"), "ms",
            "s", "m", "h".
        :param str key: Name of the key to be used or a valid PeerID,
            as listed by 'ipfs key list -l'.
        :param bool allow_offline: When offline, save the IPNS record to
            the the local datastore without broadcasting to the network
            instead of simply failing
        :param str ttl: Time duration this record should be cached for.
            Uses the same syntax as the lifetime option
        :param bool quieter: Write only final hash
        :param str ipns_base: Encoding used for keys: Can either be a
            multibase encoded CID or a base58btc encoded multihash
        """

        params = {
            ARG_PARAM: path,
            'resolve': boolarg(resolve),
            'lifetime': lifetime,
            'key': key,
            'quieter': boolarg(quieter),
            'allow-offline': boolarg(allow_offline)
        }

        if isinstance(ipns_base, str):
            params['ipns-base'] = ipns_base

        if isinstance(ttl, int):
            params['ttl'] = ttl

        return await self.fetch_json(self.url('name/publish'), params=params)

    async def resolve(self, name=None, recursive=False, nocache=False,
                      dht_record_count=None, dht_timeout=None, stream=False):
        """
        Resolve IPNS names.

        :param str name: The IPNS name to resolve. Defaults to your
            node's peerID
        :param bool recursive: Resolve until the result is not an IPNS name
        :param bool nocache: Do not use cached entries
        :param int dht_record_count: Number of records to request
            for DHT resolution
        :param int dht_timeout: Max time to collect values during DHT
            resolution eg "30s". Pass 0 for no timeout
        :param bool stream: Stream entries as they are found
        """
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
        """
        Resolve IPNS names, streaming entries as they're received
        (async generator)
        """
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

    async def diff(self, obja, objb, verbose=False):
        """
        Display the diff between two ipfs objects.
        """

        params = quote_dict({
            ARG_PARAM: [obja, objb],
            'verbose': boolarg(verbose)
        })

        return await self.fetch_json(self.url('object/diff'), params=params)

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
                  pin=True, quiet=True):
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


class RefsAPI(SubAPI):
    async def refs(self,
                   path: str,
                   format: str = None,
                   edges: bool = False,
                   unique: bool = False,
                   recursive: bool = False,
                   max_depth: int = None):
        """
        List links (references) from an object.
        """
        params = {
            ARG_PARAM: path,
            'unique': boolarg(unique),
            'recursive': boolarg(recursive),
            'edges': boolarg(edges)
        }

        if isinstance(max_depth, int):
            params['max_depth'] = str(max_depth)

        if isinstance(format, str):
            params['format'] = format

        return await self.fetch_json(self.url('refs'),
                                     params=params)

    async def local(self):
        async for ref in self.mjson_decode(self.url('refs/local')):
            yield ref


class RepoAPI(SubAPI):
    async def gc(self, quiet=False, streamerrors=False):
        params = {
            'quiet': boolarg(quiet),
            'stream-errors': boolarg(streamerrors)
        }

        async for ent in self.mjson_decode(self.url('repo/gc'),
                                           params=params):
            yield ent

    async def verify(self):
        return await self.fetch_json(self.url('repo/verify'))

    async def version(self):
        return await self.fetch_json(self.url('repo/version'))

    async def stat(self, human=False):
        return await self.fetch_json(self.url('repo/stat'),
                                     params={'human': boolarg(human)})


class RoutingAPI(SubAPI):
    async def findpeer(self, peerid, verbose=False):
        """
        Find the multiaddresses associated with a Peer ID.

        :param str peerid: The ID of the peer to search for
        :param bool verbose: Print extra information
        """
        return await self.fetch_json(
            self.url('routing/findpeer'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def findprovs(self, key, verbose=False, numproviders=20):
        """
        Find peers that can provide a specific value, given a key.

        :param str key: The key to find providers for
        :param bool verbose: Print extra information
        :param int numproviders: The number of providers to find. Default: 20
        """
        params = {
            ARG_PARAM: key,
            'verbose': boolarg(verbose),
            'num-providers': numproviders
        }

        async for value in self.mjson_decode(self.url('routing/findprovs'),
                                             params=params):
            yield value

    async def get(self, peerid, verbose=False):
        """
        Given a key, query the routing system for its best value.

        :param str key: The key to find providers for
        :param bool verbose: Print extra information
        """
        return await self.fetch_json(
            self.url('routing/get'),
            params={ARG_PARAM: peerid, 'verbose': boolarg(verbose)}
        )

    async def put(self, key, value):
        """
        Write a key/value pair to the routing system.

        :param str key: The key to store the value at
        :param bool verbose: Print extra information
        """
        return await self.fetch_json(self.url('routing/put'),
                                     params=quote_args(key, value))

    async def provide(self, key, verbose=False, recursive=False):
        """
        Announce to the network that you are providing given values.

        :param str key: The key[s] to send provide records for
        :param bool verbose: Print extra information
        :param bool recursive: Recursively provide entire graph
        """

        params = {
            ARG_PARAM: key,
            'verbose': boolarg(verbose),
            'recursive': boolarg(recursive)
        }

        async for value in self.mjson_decode(
                self.url('routing/provide'), params=params):
            yield value


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


class TarAPI(SubAPI):
    async def cat(self, key):
        """
        DEPRECATED: This command is deprecated
        """
        params = {ARG_PARAM: key}
        return await self.fetch_raw(self.url('tar/cat'),
                                    params=params)

    async def add(self, tar):
        """
        DEPRECATED: This command is deprecated
        """
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
            'nocopy',
            'only_hash',
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

        to_files = kwargs.pop('to_files', None)
        if isinstance(to_files, str) and to_files.startswith('/'):
            params['to-files'] = to_files

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
        :param str to_files: Add reference to a file inside the (MFS) at the
            provided path
        :param int inline_limit: Maximum block size to inline
        :param int cid_version: CID version
        """

        hidden = kwargs.pop('hidden', False)
        ignrulespath = kwargs.pop('ignore_rules_path', None)
        params = self._build_add_params(**kwargs)

        descriptors = []
        all_files = []
        for fitem in files:
            if isinstance(fitem, list):
                all_files += fitem
            elif isinstance(fitem, str):
                all_files.append(fitem)
            elif isinstance(fitem, Path):
                all_files.append(str(fitem))

        # Build the multipart form and add the files/directories
        with multi.FormDataWriter() as mpwriter:
            for filepath in all_files:
                await asyncio.sleep(0)

                if not isinstance(filepath, str):
                    continue

                if not os.path.exists(filepath):
                    continue

                if os.path.isdir(filepath):
                    dir_listing = multi.DirectoryListing(
                        filepath, hidden=hidden,
                        ignrulespath=ignrulespath)
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

                        descriptors.append(_fd)
                else:
                    basename = os.path.basename(filepath)
                    _fd = open(filepath, 'rb')

                    file_payload = payload.BytesIOPayload(
                        _fd,
                        content_type='application/octet-stream',
                        headers={
                            'Abspath': filepath
                        }
                    )

                    file_payload.set_content_disposition('form-data',
                                                         name='file',
                                                         filename=basename)
                    mpwriter.append_payload(file_payload)
                    descriptors.append(_fd)

            if mpwriter.size == 0:
                raise aioipfs.UnknownAPIError('Multipart is empty')

            try:
                async for value in self.add_generic(mpwriter, params=params):
                    yield value
            except Exception as err:
                for fd in descriptors:
                    try:
                        fd.close()
                    except Exception:
                        continue

                raise err

    async def commands(self, flags=False):
        """ List all available commands."""

        return await self.fetch_json(
            self.url('commands'),
            params={'flags': boolarg(flags)}
        )

    async def id(self, peer: str = None,
                 format: str = None,
                 peerid_base: str = None):
        """
        Show IPFS node id info.

        :param str peer: peer id to look up, otherwise shows local node info
        """
        params = {ARG_PARAM: peer} if peer else {}

        if isinstance(format, str):
            params['format'] = format

        if isinstance(peerid_base, str):
            params['peerid-base'] = peerid_base

        return await self.fetch_json(self.url('id'), params=params)

    async def cat(self, path, offset=None, length=None):
        """
        Show IPFS object data.

        :param str path: The path of the IPFS object to retrieve
        :param int offset: byte offset to begin reading from
        :param int length: maximum number of bytes to read
        """

        params = {ARG_PARAM: path}

        if offset is not None and isinstance(offset, int):
            params['offset'] = offset
        if length is not None and isinstance(length, int):
            params['length'] = length

        return await self.fetch_raw(self.url('cat'), params=params)

    def _extract_tar(self, archive_path: str, dstdir: str, compress: bool):
        # Synchronous tar extraction runs in the executor

        mode = 'r|gz' if compress is True else 'r|'

        def remove_archive():
            try:
                os.unlink(archive_path)
            except Exception as err:
                print('Could not remove TAR file:', str(err), file=sys.stderr)

        try:
            with tarfile.open(name=archive_path, mode=mode) as tf:
                tf.extractall(path=dstdir)
        except Exception as err:
            print('Could not extract TAR file:', str(err), file=sys.stderr)
            remove_archive()
            return False
        else:
            remove_archive()
            return True

    async def get(self, path, dstdir='.', compress=False,
                  compression_level=-1, archive=True, output=None,
                  progress_callback=None, progress_callback_arg=None,
                  chunk_size=16384):
        """
        Download IPFS objects.

        :param str path: The path of the IPFS object to retrieve
        :param str dstdir: destination directory, current directory by default
        :param bool compress: Compress the output with GZIP compression
        :param str compression_level: The level of compression (1-9)
        :param bool archive: Output a TAR archive
        """

        params = {
            ARG_PARAM: path,
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
            async with self.driver.session.post(self.url('get'),
                                                params=params) as response:
                if response.status != 200:
                    raise aioipfs.APIError(http_status=response.status)

                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break

                    read_so_far += len(chunk)

                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(path, read_so_far,
                                                progress_callback_arg)

                    await fd.write(chunk)
                    await asyncio.sleep(0)

                await response.release()

        # Run the tar extraction inside asyncio's threadpool
        loop = asyncio.get_event_loop()
        tar_future = loop.run_in_executor(
            None, self._extract_tar,
            archive_path, dstdir, compress)
        return await tar_future

    async def getgen(self, objpath, dstdir='.', compress=False,
                     compression_level=-1, archive=True, output=None,
                     progress_callback=None, progress_callback_arg=None,
                     sleept=0.05, chunk_size=16384):
        """
        Download IPFS objects (async generator)

        :param str objpath: The base58 objpath of the object to retrieve
        :param str dstdir: destination directory, current directory by default
        :param bool compress: Compress the output with GZIP compression
        :param str compression_level: The level of compression (1-9)
        :param bool archive: Output a TAR archive
        """

        params = {
            ARG_PARAM: objpath,
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
        chunks = 0

        try:
            async with aiofiles.open(archive_path, 'wb') as fd:
                async with self.driver.session.post(self.url('get'),
                                                    params=params) as response:
                    if response.status != 200:
                        raise aioipfs.APIError(http_status=response.status)

                    headers = response.headers
                    clength = int(headers.get('X-Content-Length'))

                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break

                        chunks += 1
                        read_so_far += len(chunk)

                        yield 0, read_so_far, clength

                        await fd.write(chunk)
                        await asyncio.sleep(sleept)

                    await response.release()
        except GeneratorExit:
            os.unlink(archive_path)
            raise
        except Exception:
            os.unlink(archive_path)
            raise
        else:
            # Run the tar extraction inside asyncio's threadpool
            loop = asyncio.get_event_loop()
            tar_future = loop.run_in_executor(
                None, self._extract_tar,
                archive_path, dstdir, compress)
            res = await tar_future

            if res is True:
                yield 1, None, None
            else:
                yield -1, None, None

    async def ls(self, path, headers=False, resolve_type=True,
                 size: bool = True,
                 stream: bool = False):
        """
        List directory contents for Unix filesystem objects.

        :param str path: The path to the IPFS object(s) to list links from
        :param bool headers: Print table headers (Hash, Size, Name)
        :param bool resolve_type: Resolve linked objects to get their types
        """

        params = {
            'resolve-type': boolarg(resolve_type),
            'headers': boolarg(headers),
            'size': boolarg(size),
            'stream': boolarg(stream),
            ARG_PARAM: path
        }
        return await self.fetch_json(self.url('ls'), params=params)

    async def ls_streamed(self, path, headers=False, resolve_type=True):
        """
        List directory contents for Unix filesystem objects (streamed)

        :param str path: The path to the IPFS object(s) to list links from
        :param bool headers: Print table headers (Hash, Size, Name)
        :param bool resolve_type: Resolve linked objects to get their types
        """

        params = {
            'resolve-type': boolarg(resolve_type),
            'headers': boolarg(headers),
            'stream': boolarg(True),
            ARG_PARAM: path
        }

        async for value in self.mjson_decode(
                self.url('ls'), params=params):
            yield value

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

    async def version_deps(self):
        """
        Shows information about dependencies used for build
        """
        return await self.fetch_json(self.url('version/deps'))

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

    async def resolve(self, name,
                      recursive: bool = False,
                      dht_record_count: int = None,
                      dht_timeout: int = None):
        """
        Resolve the value of names to IPFS

        :param str name: The name to resolve
        :param bool recursive: Resolve until the result is an IPFS name
        :param int dht_record_count: Number of records to request
            for DHT resolution
        :param int dht_timeout: Max time to collect values during DHT
            resolution eg "30s". Pass 0 for no timeout
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
