import base64
import pytest

import tempfile
import random
import string
import time
import subprocess
import os
import os.path
import platform
import json
import tarfile
import sys

from pathlib import Path
from multiaddr import Multiaddr

import asyncio
import aioipfs

from aioipfs import util
from aioipfs.multi import DirectoryListing


def ipfs_config_get():
    p = subprocess.Popen(['ipfs', 'config', 'show'],
                         stdout=subprocess.PIPE)
    out, err = p.communicate()

    try:
        cfg = json.loads(out.decode())
    except Exception:
        return None
    else:
        return util.DotJSON(cfg)


def ipfs_config_replace(filep: str):
    p = subprocess.Popen(['ipfs', 'config', 'replace', filep])
    p.communicate()
    return p.returncode


def ipfs_getconfig_var(var):
    sp_getconfig = subprocess.Popen(['ipfs', 'config',
                                     var], stdout=subprocess.PIPE)
    stdout, stderr = sp_getconfig.communicate()
    return stdout.decode()


@pytest.fixture
def datafiles():
    return Path(os.path.dirname(__file__)).joinpath('datafiles')


@pytest.fixture
def smalltar():
    fd, tpath = tempfile.mkstemp()
    tar = tarfile.open(tpath, 'w|')
    tar.add(__file__)
    tar.close()
    yield tar, tpath

    os.close(fd)
    os.unlink(tpath)


@pytest.fixture
def testfile1(tmpdir):
    filep = tmpdir.join('testfile1.txt')
    filep.write('POIEKJDOOOPIDMWOPIMPOWE()=ds129084bjcy')
    return filep


@pytest.fixture
def testfile2(tmpdir):
    r = random.Random()
    filep = tmpdir.join('testfile2.txt')
    filep.write(''.join([str(r.randint(i, i * 2)) for i in range(0, 16)]))
    return filep


def random_word(length=8):
    return ''.join(
        random.choice(string.ascii_lowercase) for c in range(length))


@pytest.fixture
def dir_hierarchy1(tmpdir):
    root = Path(str(tmpdir))
    root.joinpath('a/b/.c').mkdir(parents=True)
    root.joinpath('a/b/.c/file0').touch()
    root.joinpath('d/.e/f').mkdir(parents=True)
    root.joinpath('d/.e/f/.file3').touch()
    root.joinpath('file1').touch()
    root.joinpath('.file2').touch()
    return str(root)


@pytest.fixture
def dir_hierarchy2(tmpdir):
    root = Path(str(tmpdir))
    root.joinpath('a/b/.c').mkdir(parents=True)
    root.joinpath('d/.e/f').mkdir(parents=True)
    root.joinpath('d/.e/f/.file3').touch()
    root.joinpath('file1').touch()

    readme = root.joinpath('README.txt')
    readme.touch()

    with open(readme, 'wt') as f:
        f.write('Hello')

    root.joinpath('README2.txt').touch()
    root.joinpath('.file2').touch()
    ign = root.joinpath('.gitignore')
    ign.touch()
    ign.write_text("README.txt\n.file2\na\na/**\nd/.e/*/*\nd/.e/f\n")
    return root


def ipfs_config(param, value):
    os.system('ipfs config {0} "{1}"'.format(param, value))


def ipfs_config_json(param, value):
    os.system("ipfs config --json '{0}' '{1}'".format(
        param, json.dumps(value)))


apiport = 9001
gwport = 9080
swarmport = 9002


@pytest.fixture(scope='module')
def ipfsdaemon():
    # Starts a daemon on high port and temporary directory, yield it
    # when started and shut it down on fixture's exit

    tmpdir = tempfile.mkdtemp()

    # Setup IPFS_PATH and initialize the repository
    os.putenv('IPFS_PATH', tmpdir)
    os.system('ipfs init -e')

    cfg = ipfs_config_get()

    with tempfile.NamedTemporaryFile(mode='wt', delete=False) as ncfgf:
        cfg.Addresses.API = [
            f'/ip4/127.0.0.1/tcp/{apiport}',
            f'/ip6/::1/tcp/{apiport}',
        ]

        cfg.Addresses.Gateway = f'/ip4/127.0.0.1/tcp/{gwport}'
        cfg.Addresses.Swarm = [f"/ip4/127.0.0.1/tcp/{swarmport}"]

        # Empty bootstrap so we're not bothered
        cfg.Bootstrap = []

        cfg.Experimental.Libp2pStreamMounting = True
        cfg.Experimental.FilestoreEnabled = True

        cfg.write(ncfgf)

    ipfs_config_replace(ncfgf.name)

    # Run the daemon and wait a bit
    sp = subprocess.Popen(['ipfs', 'daemon', '--enable-pubsub-experiment'],
                          stdout=subprocess.PIPE)
    time.sleep(1)

    yield tmpdir, sp

    time.sleep(0.5)
    # Cleanup
    sp.terminate()


@pytest.fixture
def ipfs_peerid(ipfsdaemon):
    return ipfs_getconfig_var('Identity.PeerID').strip()


@pytest.fixture(autouse=True)
async def iclient(event_loop):
    client = aioipfs.AsyncIPFS(port=apiport, loop=event_loop)
    yield client
    await client.close()


class TestClientConstructor:
    @pytest.mark.asyncio
    async def test_invalid_constructor(self, event_loop):
        # Invalid host
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(host=None, loop=event_loop)

        # Invalid port
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(host='localhost', port=None, loop=event_loop)

        # Invalid multiaddr
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='invalid', loop=event_loop)

        # Incomplete multiaddrs
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='/ip4/127.0.0.1', loop=event_loop)

        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='/ip6/::1', loop=event_loop)

        # 'localhost' is not a valid IPv4 for the ip4 codec
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='/ip4/localhost/tcp/8000', loop=event_loop)

        # UDP protocol is of course not supported for the RPC
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='/ip4/127.0.0.1/udp/4000', loop=event_loop)

        # Invalid application layer protocol
        with pytest.raises(aioipfs.InvalidNodeAddressError):
            aioipfs.AsyncIPFS(maddr='/ip4/localhost/tcp/4000/invalid',
                              loop=event_loop)

    @pytest.mark.asyncio
    async def test_constructor_apiurl(self, event_loop, ipfsdaemon):
        # Test by passing a host and port
        client = aioipfs.AsyncIPFS(
            host='localhost', port=apiport, loop=event_loop)

        assert str(client.api_url) == f'http://localhost:{apiport}/api/v0/'

        # Test by passing a host, port and scheme
        client = aioipfs.AsyncIPFS(
            host='localhost', port=apiport, scheme='https', loop=event_loop)

        assert str(client.api_url) == f'https://localhost:{apiport}/api/v0/'

        # Test by passing a valid /ip4/x.x.x.x/tcp/port multiaddr
        client = aioipfs.AsyncIPFS(
            maddr=f'/ip4/127.0.0.1/tcp/{apiport}', loop=event_loop)

        assert str(client.api_url) == f'http://127.0.0.1:{apiport}/api/v0/'

        # Test by passing a valid /dns4/host/tcp/port multiaddr
        client = aioipfs.AsyncIPFS(
            maddr=f'/dns4/localhost/tcp/{apiport}'
        )
        assert str(client.api_url) == f'http://localhost:{apiport}/api/v0/'

        # Test by passing a valid /dns6/host/tcp/port multiaddr
        client = aioipfs.AsyncIPFS(
            maddr=f'/dns6/example.com/tcp/{apiport}'
        )
        assert str(client.api_url) == f'http://example.com:{apiport}/api/v0/'

        # Test by passing a valid HTTPS multiaddr
        client = aioipfs.AsyncIPFS(
            maddr=f'/dns4/localhost/tcp/{apiport}/https', loop=event_loop)

        assert str(client.api_url) == f'https://localhost:{apiport}/api/v0/'

        # Test by passing a valid /ip6/.../tcp/port multiaddr
        client = aioipfs.AsyncIPFS(
            maddr=f'/ip6/::1/tcp/{apiport}', loop=event_loop)

        assert str(client.api_url) == f'http://[::1]:{apiport}/api/v0/'

        # Test request via IPv6
        info = await client.id()
        assert 'ID' in info

        # Test by passing a Multiaddr instance
        client = aioipfs.AsyncIPFS(
            maddr=Multiaddr(f'/ip4/127.0.0.1/tcp/{apiport}')
        )

        assert str(client.api_url) == f'http://127.0.0.1:{apiport}/api/v0/'

        # The default constructor should always use localhost:5001
        client = aioipfs.AsyncIPFS()
        assert str(client.api_url) == 'http://localhost:5001/api/v0/'


class TestAsyncIPFS:
    @pytest.mark.asyncio
    async def test_basic(self, event_loop, ipfsdaemon, iclient):
        tmpdir, sp = ipfsdaemon
        await iclient.id()
        await iclient.core.version()
        await iclient.commands()

    @pytest.mark.asyncio
    async def test_bootstrap(self, event_loop, ipfsdaemon, iclient):
        tmpdir, sp = ipfsdaemon
        await iclient.bootstrap.list()

    @pytest.mark.asyncio
    async def test_swarm(self, event_loop, ipfsdaemon, iclient):
        await iclient.swarm.peers()
        await iclient.swarm.addrs()
        await iclient.swarm.addrs_local()
        await iclient.swarm.addrs_listen()

    @pytest.mark.asyncio
    async def test_swarm_resources(self, event_loop, ipfsdaemon, iclient):
        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.20.0'):
            # /api/v0/swarm/resources was introduced in kubo v0.19.0
            pytest.skip('RPC endpoint not available')

        assert 'System' in await iclient.swarm.resources()

    @pytest.mark.asyncio
    async def test_swarm_peering(self, event_loop, ipfsdaemon, iclient):
        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.12.0'):
            # Unavailable for these versions
            pytest.skip('RPC endpoints not available')

        info = await iclient.id()
        reply = await iclient.swarm.peering.ls()
        assert 'Peers' in reply

        with pytest.raises(aioipfs.APIError):
            await iclient.swarm.peering.add(info['ID'])

        with pytest.raises(aioipfs.APIError):
            await iclient.swarm.peering.rm('nothere')

    @pytest.mark.asyncio
    async def test_refs(self, event_loop, ipfsdaemon, iclient,
                        testfile1):
        # TODO: proper refs test from an object
        cids = [added['Hash'] async for added in iclient.add(str(testfile1))]
        await iclient.refs.refs(cids.pop(),
                                max_depth=-1)

        async for refobj in iclient.refs.local():
            assert 'Ref' in refobj

    @pytest.mark.asyncio
    async def test_block1(self, event_loop, ipfsdaemon, iclient, testfile1):
        reply = await iclient.block.put(testfile1)
        data = await iclient.block.get(reply['Key'])
        assert data.decode() == testfile1.read()

    @pytest.mark.asyncio
    async def test_add(self, event_loop, ipfsdaemon, iclient, testfile1,
                       testfile2):
        count = 0
        async for added in iclient.add(str(testfile1)):
            assert 'Hash' in added
            count += 1

        assert count == 1
        count = 0
        all = [[str(testfile1), str(testfile2)]]

        async for added in iclient.add(*all):
            assert 'Hash' in added
            count += 1

        assert count == 2

        # Test the new --to-files argument introduced by
        # kubo v0.16.0, which allows to link the
        # imported file in the MFS space in the same RPC call

        if await iclient.agent_version_get() >= \
                aioipfs.IpfsDaemonVersion('0.16.0'):
            async for added in iclient.add(str(testfile2),
                                           to_files='/mfsref'):
                assert 'Hash' in added

            content = await iclient.files.read('/mfsref')
            assert content.decode() == testfile2.read()

            # This fails, as --to-files requires a MFS path starting with /
            await iclient.add_str('invalid', to_files='noslash')
            with pytest.raises(aioipfs.APIError):
                await iclient.files.read('/noslash')

            # Valid MFS path
            await iclient.add_str('test', to_files='/wslash')
            assert (await iclient.files.read('/wslash')).decode() == 'test'

    @pytest.mark.asyncio
    async def test_hidden(self, event_loop, ipfsdaemon, iclient,
                          dir_hierarchy1):
        async for added in iclient.add(dir_hierarchy1, hidden=False):
            parts = added['Name'].split('/')
            for part in parts:
                assert not part.startswith('.')

        names = []
        async for added in iclient.add(dir_hierarchy1, hidden=True):
            names.append(added['Name'])

        assert 'test_hidden0/d/.e/f/.file3' in names
        assert 'test_hidden0/a/b/.c' in names

    @pytest.mark.asyncio
    async def test_ignorerules(self, event_loop, ipfsdaemon, iclient,
                               dir_hierarchy2):
        names = []
        async for added in iclient.add(str(dir_hierarchy2),
                                       ignore_rules_path='.gitignore',
                                       hidden=True):
            names.append(added['Name'])

        assert 'test_ignorerules0/.gitignore' in names
        assert 'test_ignorerules0/.file2' not in names
        assert 'test_ignorerules0/a' not in names
        assert 'test_ignorerules0/d/.e/f' not in names
        assert 'test_ignorerules0/README.txt' not in names
        assert 'test_ignorerules0/README2.txt' in names

        names = []
        async for added in iclient.add(str(dir_hierarchy2),
                                       ignore_rules_path='.gitignore',
                                       hidden=False):
            names.append(added['Name'])

        assert 'test_ignorerules0/.gitignore' in names

    @pytest.mark.asyncio
    async def test_addtar(self, event_loop, ipfsdaemon, iclient,
                          tmpdir, smalltar):
        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.26.0'):
            tar, tarpath = smalltar
            reply = await iclient.tar.add(tarpath)
            tarhash = reply['Hash']
            fetched = await iclient.tar.cat(tarhash)
            f = tmpdir.join('new.tar')
            f.write(fetched)

    @pytest.mark.asyncio
    @pytest.mark.parametrize('order', ['gin', 'tonic'])
    @pytest.mark.parametrize('second', ['beer', 'wine'])
    async def test_addjson(self, event_loop, ipfsdaemon, iclient,
                           order, second):
        json1 = {
            'random': 'stuff',
            'order': order,
            'second': second
        }

        reply = await iclient.add_json(json1)
        h = reply['Hash']

        data = await iclient.cat(h)
        assert data.decode() == json.dumps(json1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'234098dsfkj2doidf0'])
    async def test_addbytes(self, event_loop, ipfsdaemon, iclient, data):
        reply = await iclient.add_bytes(data, cid_version=1, hash='sha2-256')
        assert reply['Hash'] == \
            'bafkreiewqrl3s3cgd4ll3wybtrxv7futfksuylocfxzlugbjparmyyt6eq'

        catD = await iclient.cat(reply['Hash'])
        assert catD == data

        reply = await iclient.add_bytes(data, cid_version=1, hash='sha2-512')
        assert reply['Hash'] == 'bafkrgqdao6vujlzh4z6o7mzgv3jnydftv2of5jy32yufswk7bnvwaq7oyaizo6gnditr4okfphi2cguz2cack27rsjfzuybm57knagzjl6m34'  # noqa

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'234098dsfkj2doidf0'])
    async def test_dag(self, event_loop, ipfsdaemon, iclient, tmpdir, data):
        # More tests needed here
        entry = await iclient.add_bytes(data)
        jsondag = {'dag': {'/': entry['Hash']}}
        filedag = tmpdir.join('jsondag.txt')
        filedag.write(json.dumps(jsondag))

        reply = await iclient.dag.put(filedag)
        assert 'Cid' in reply

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'234098dsfkj2doidf0'])
    async def test_car(self, event_loop, ipfsdaemon, iclient, tmpdir, data):
        entry = await iclient.add_bytes(data)
        jsondag = {'dag': {'/': entry['Hash']}}
        filedag = tmpdir.join('jsondag.txt')
        filedag.write(json.dumps(jsondag))

        reply = await iclient.dag.put(filedag)
        assert 'Cid' in reply

        export = await iclient.dag.car_export(reply['Cid']['/'])
        assert isinstance(export, bytes)

        imported = await iclient.dag.car_import(export)
        assert imported['Root']['Cid']['/'] is not None
        assert reply['Cid']['/'] == imported['Root']['Cid']['/']

        carfd, filecar = tempfile.mkstemp()
        with open(filecar, 'wb') as fd:
            fd.write(export)

        imported = await iclient.dag.car_import(filecar)
        assert imported['Root']['Cid']['/'] is not None
        assert reply['Cid']['/'] == imported['Root']['Cid']['/']

        os.close(carfd)
        os.unlink(filecar)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.version_info < (3, 11),
                        reason='Need python >= 3.11 for CAR decoding')
    async def test_car_fs_export(self, event_loop, ipfsdaemon, iclient,
                                 tmpdir, testfile1):
        """
        Test unpacking a UnixFS CAR export to a directory
        by using the /dag/export endpoint
        """

        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.20.0'):
            pytest.skip('Not testing CAR export for this version of kubo')

        dst = Path(tmpdir).joinpath('unpacked')
        dst.mkdir(parents=True, exist_ok=True)

        cids = [added['Hash'] async for added in
                iclient.add(str(testfile1), wrap=True, cid_version=1)]
        top_cid = cids[-1]

        path = Path(tmpdir).joinpath('export.car')
        await iclient.dag.export(top_cid, output_path=path)

        assert path.is_file()

        # Test the function that reads a CAR file
        stream = util.car_open(path)
        assert stream

        data = await util.car_bytes(stream, top_cid)
        assert data == b'POIEKJDOOOPIDMWOPIMPOWE()=ds129084bjcy'

        assert await iclient.dag.export_to_directory(top_cid, dst) is True

        fp = dst.joinpath(cids[0])
        assert fp.is_file()
        assert fp.read_text() == 'POIEKJDOOOPIDMWOPIMPOWE()=ds129084bjcy'

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == 'Windows',
                        reason='This kubo API is not available on your OS')
    async def test_diag(self, event_loop, ipfsdaemon, iclient, tmpdir):
        reply = await iclient.diag.sys()
        assert 'diskinfo' in reply

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'0123456789'])
    async def test_catoffset(self, event_loop, ipfsdaemon, iclient,
                             tmpdir, data):
        entry = await iclient.add_bytes(data)
        raw = await iclient.cat(entry['Hash'], offset=4)
        assert raw.decode() == '456789'
        raw = await iclient.cat(entry['Hash'], offset=2, length=3)
        assert raw.decode() == '234'

    @pytest.mark.asyncio
    async def test_get(self, event_loop, ipfsdaemon,
                       iclient, testfile2, tmpdir):
        cid: str = None

        async for reply in iclient.add(str(testfile2)):
            cid = reply['Hash']

        result = await iclient.get(cid, dstdir=tmpdir)

        assert result is True
        assert cid in os.listdir(tmpdir)

    @pytest.mark.asyncio
    async def test_multiget(self, event_loop, ipfsdaemon,
                            iclient, testfile2, tmpdir):
        hashes = []

        # Create 16 variations of testfile2 and add them to the node
        for idx in range(0, 16):
            testfile2.write('ABCD' + str(idx))
            async for reply in iclient.add(str(testfile2)):
                hashes.append(reply['Hash'])

        # Get them all back concurrently
        tasks = [iclient.get(hash, dstdir=tmpdir) for hash in hashes]
        await asyncio.gather(*tasks)

        for hash in hashes:
            async for result in iclient.getgen(hash, dstdir=tmpdir):
                status, read, clength = result
                assert status in [0, 1]

    @pytest.mark.asyncio
    async def test_multibase(self, event_loop, ipfsdaemon, iclient,
                             tmpdir, testfile1):
        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.10.0'):
            # the /multibase  endpoints were introduced some time around
            # v0.10.x or v0.11x, don't test this API in that case

            with pytest.raises(aioipfs.EndpointNotFoundError):
                await iclient.multibase.list()

            pytest.skip('RPC endpoints not available')

        reply = await iclient.multibase.list()
        assert isinstance(reply, list)
        assert len(reply) > 0

        reply = await iclient.multibase.encode(str(testfile1))
        encp = tmpdir.join('encoded')
        encp.write(reply)
        assert reply == 'uUE9JRUtKRE9PT1BJRE1XT1BJTVBPV0UoKT1kczEyOTA4NGJqY3k'

        reply = await iclient.multibase.decode(str(encp))
        assert isinstance(reply, str)
        reply = await iclient.multibase.transcode(str(encp))
        assert isinstance(reply, str)

    @pytest.mark.asyncio
    @pytest.mark.parametrize('topic', ['aioipfs.pytest'])
    @pytest.mark.parametrize('msgdata', ['test',
                                         b'amazing',
                                         None,
                                         1234])
    async def test_pubsub(self, event_loop, ipfsdaemon, iclient,
                          topic, msgdata):
        # Listen on a pubsub topic and send a single message, checking that
        # the multibase decoding is correctly done

        info = await iclient.id()

        await iclient.pubsub.peers()

        async def subtask():
            try:
                async for message in iclient.pubsub.sub(topic):
                    if isinstance(message['from'], bytes):
                        # Old base58 messages: from is bytes
                        assert message['from'].decode() == info['ID']
                    elif isinstance(message['from'], str):
                        assert message['from'] == info['ID']
                    else:
                        raise Exception('PS from value is invalid')

                    assert message['topicIDs'] == [topic]

                    if isinstance(msgdata, bytes):
                        assert message['data'].decode() == msgdata.decode()
                    else:
                        assert message['data'].decode() == msgdata
            except AssertionError as err:
                print(f'Pubsub message assert error: {err}')
                return False
            except asyncio.CancelledError:
                return True

            return False

        if type(msgdata) not in [bytes, str]:
            with pytest.raises(ValueError):
                await iclient.pubsub.pub(topic, msgdata)

            pytest.skip(
                f'Skipping complete message pubsub test for invalid '
                f'message type: {type(msgdata)}'
            )

        t = asyncio.ensure_future(subtask())

        await asyncio.sleep(2)

        topics = (await iclient.pubsub.ls())['Strings']
        assert topic in topics  # should always work, as topics are decoded
        peers = await iclient.pubsub.peers()
        assert 'Strings' in peers

        await iclient.pubsub.pub(topic, msgdata)
        await asyncio.sleep(1)

        t.cancel()
        await asyncio.sleep(0.5)
        assert t.result() is True

    @pytest.mark.asyncio
    async def test_routing(self, event_loop, ipfsdaemon, iclient):
        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.14.0'):
            with pytest.raises(aioipfs.EndpointNotFoundError):
                await iclient.routing.get('whoknows')

            pytest.skip('RPC endpoints not available')

        reply = await iclient.add_bytes(b'ABCD', cid_version=1,
                                        hash='sha2-256')
        provs = [p async for p in iclient.routing.findprovs(reply['Hash'])]
        assert len(provs) > 0

    @pytest.mark.asyncio
    async def test_stats(self, event_loop, ipfsdaemon, iclient):
        await iclient.stats.bw()
        await iclient.stats.bitswap()
        await iclient.stats.repo()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('protocol', ['/x/test'])
    @pytest.mark.parametrize('address', ['/ip4/127.0.0.1/tcp/10000'])
    async def test_p2p(self, event_loop, ipfsdaemon, iclient, protocol,
                       address):
        await iclient.p2p.listen(protocol, address)
        listeners = await iclient.p2p.listener_ls(headers=True)
        assert len(listeners['Listeners']) > 0

        listener = listeners['Listeners'].pop()
        assert listener['Protocol'] == protocol

        if 'Address' in listener:
            # Pre 0.4.18
            assert listener['Address'] == address
        elif 'TargetAddress' in listener:
            # Post 0.4.18
            assert listener['TargetAddress'] == address

        await iclient.p2p.listener_close(protocol)
        listeners = await iclient.p2p.listener_ls()
        assert listeners['Listeners'] is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize('protocol', ['/x/test'])
    @pytest.mark.parametrize('address', ['/ip4/127.0.0.1/tcp/10000'])
    async def test_p2p_dial(self, event_loop, ipfsdaemon, iclient,
                            protocol, address):
        nid = (await iclient.core.id())['ID']
        await iclient.p2p.listen(protocol, address)

        async with iclient.p2p.dial_service(nid, protocol,
                                            allow_loopback=True) as ctx:
            assert ctx.maddr == Multiaddr(address)

    @pytest.mark.asyncio
    @pytest.mark.parametrize('keysize', [2048, 4096])
    async def test_keys(self, event_loop, ipfsdaemon, iclient,
                        keysize, datafiles):
        keyname = random_word()

        reply = await iclient.key.gen(keyname, size=keysize)
        assert reply['Name'] == keyname
        key_hash = reply['Id']

        reply = await iclient.key.list()
        names = [k['Name'] for k in reply['Keys']]
        assert keyname in names

        removed = await iclient.key.rm(keyname)
        assert removed['Keys'].pop()['Id'] == key_hash

        # Key import test
        impname = random_word()
        reply = await iclient.key.key_import(
            str(datafiles.joinpath('ipns-key1')),
            impname
        )
        assert reply['Name'] == impname

    @pytest.mark.asyncio
    async def test_bitswap(self, event_loop, ipfsdaemon, iclient):
        await iclient.bitswap.wantlist()
        stats = await iclient.bitswap.stat()
        assert 'Wantlist' in stats
        assert 'DataSent' in stats

    @pytest.mark.asyncio
    async def test_filestore(self, event_loop, ipfsdaemon, iclient):
        await iclient.filestore.dups()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('obj', [b'0123456789'])
    async def test_files_rw(self, event_loop, ipfsdaemon, iclient, obj,
                            testfile1, testfile2):
        # Write obj (bytes) to /test1
        await iclient.files.write('/test1', obj, create=True)
        data = await iclient.files.read('/test1')
        assert data == obj

        # Write testfile1 to /test2
        await iclient.files.write('/test2', str(testfile1), create=True)
        data = await iclient.files.read('/test2')
        filedata = testfile1.read()
        assert data.decode() == filedata

        # Write testfile2 to /test3, then write 123 at some offset
        # and read the file again starting from that offset
        await iclient.files.write('/test3', str(testfile2), create=True)
        otro = b'123'
        await iclient.files.write('/test3', otro, create=True,
                                  offset=5)
        data = await iclient.files.read('/test3', offset=5, count=3)
        assert data == otro

    @pytest.mark.asyncio
    @pytest.mark.parametrize('obj', [b'0123456789'])
    async def test_files_cp(self, event_loop, ipfsdaemon, iclient, obj):
        await iclient.files.write('/test8', obj, create=True)
        await iclient.files.cp('/test8', '/test9')

        files = await iclient.files.ls('/')
        names = [e['Name'] for e in files['Entries']]
        assert 'test8' in names
        assert 'test9' in names

        data = await iclient.files.read('/test9')
        assert data == obj

    @pytest.mark.asyncio
    @pytest.mark.parametrize('obj1', [b'0123456789'])
    @pytest.mark.parametrize('obj2', [b'0a1b2c3d4e5'])
    async def test_object(self, event_loop, ipfsdaemon, iclient, obj1, obj2,
                          testfile2):
        """ Unsure if this is correct """
        obj1Ent = await iclient.add_bytes(obj1)
        obj2Ent = await iclient.add_bytes(obj2)
        obj = await iclient.object.new()
        r1 = await iclient.object.patch.add_link(obj['Hash'], 'obj1',
                                                 obj1Ent['Hash'])
        r2 = await iclient.object.patch.add_link(r1['Hash'], 'obj2',
                                                 obj2Ent['Hash'])
        diff = await iclient.object.diff(r2['Hash'], obj['Hash'], verbose=True)
        assert 'Changes' in diff
        assert len(diff['Changes']) == 2

        dag = await iclient.object.get(r2['Hash'])
        assert len(dag['Links']) == 2
        data1 = await iclient.cat(dag['Links'][0]['Hash'])
        data2 = await iclient.cat(dag['Links'][1]['Hash'])

        assert data1 == obj1
        assert data2 == obj2

        with pytest.raises(aioipfs.NoSuchLinkError) as exc:
            await iclient.object.patch.rm_link(obj['Hash'], 'obj1')

        assert exc.value.message == 'no link by that name'

        rm = await iclient.object.patch.rm_link(r2['Hash'], 'obj1')
        dag = await iclient.object.get(rm['Hash'])
        assert len(dag['Links']) == 1

    @pytest.mark.asyncio
    async def test_name_inspect(self, event_loop, ipfsdaemon, iclient):
        """
        Run name inspect on the node's IPNS key
        """

        if await iclient.agent_version_get() < \
                aioipfs.IpfsDaemonVersion('0.20.0'):
            # /api/v0/name/inspect was introduced in kubo v0.19.0
            pytest.skip('RPC endpoint not available')

        nid = (await iclient.id())['ID']
        record = await iclient.routing.get(f'/ipns/{nid}')

        with open('ipnsr.bin', 'w+b') as ipnsr:
            ipnsr.write(base64.b64decode(record['Extra']))

        result = await iclient.name.inspect('ipnsr.bin')
        assert result['Entry']['Value']
        assert result['Entry']['Validity']

        # Try by passing a Path
        result = await iclient.name.inspect(Path('ipnsr.bin'))
        assert 'Entry' in result
        assert result['Entry']['Value']
        assert result['Entry']['Validity']

        # Pass an invalid value type
        with pytest.raises(ValueError):
            await iclient.name.inspect(42)

    @pytest.mark.asyncio
    async def test_config(self, event_loop, ipfsdaemon, iclient, tmpdir):
        conf = await iclient.config.show()
        assert 'API' in conf
        sameconf = tmpdir.join('config.json')
        sameconf.write(json.dumps(conf))
        await iclient.config.replace(str(sameconf))

        await iclient.config.config(
            'Datastore.StorageGCWatermark', value=150,
            json=True
        )

        await iclient.config.config(
            'Datastore.HashOnRead', value=True,
            boolean=True
        )

        result = await iclient.config.config('Datastore.StorageGCWatermark')
        assert result['Value'] == 150

        result = await iclient.config.config('Datastore.HashOnRead')
        assert result['Value'] is True

        result = await iclient.config.config('Bootstrap')
        assert result['Value'] == []

    @pytest.mark.asyncio
    async def test_cidapi(self, event_loop, ipfsdaemon, iclient, testfile1):
        async for added in iclient.add(str(testfile1), cid_version=1):
            multihash = added['Hash']
            reply = await iclient.cid.base32(multihash)
            assert reply['CidStr'] == multihash
            assert 'Formatted' in reply

            await iclient.cid.format(multihash, version=0)

        await iclient.cid.codecs()
        await iclient.cid.bases()
        await iclient.cid.hashes()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('pin_name', ['pintest'])
    async def test_pin(self, event_loop, ipfsdaemon, iclient, pin_name):
        entry = await iclient.add_bytes(b'Test', pin=False)

        if await iclient.agent_version_get() >= \
                aioipfs.IpfsDaemonVersion('0.26.0'):
            """
            kubo >= 0.26.0 supports optional pin names

            Pin the object with a pin name and check that the entry
            has the correct name when listing the pins
            """

            resp = [e async for e in iclient.pin.add(
                entry['Hash'],
                name=pin_name
            )]
            assert len(resp) > 0

            pins = await iclient.pin.ls(names=True)
            pine = pins['Keys'].get(entry['Hash'])

            assert pine['Name'] == pin_name
        else:
            resp = [e async for e in iclient.pin.add(entry['Hash'])]
            assert len(resp) > 0

    @pytest.mark.asyncio
    @pytest.mark.skip(reason='This test relies on specific network conditions')
    @pytest.mark.parametrize('srvname', ['mysrv1'])
    @pytest.mark.parametrize('srvendpoint',
                             ['https://api.estuary.tech/pinning'])
    async def test_pin_remote(self, event_loop, ipfsdaemon, iclient,
                              srvname, srvendpoint):
        res = await iclient.pin.remote.service.add(
            srvname,
            srvendpoint,
            'mykey'
        )

        res = await iclient.pin.remote.service.ls()
        assert 'RemoteServices' in res
        service = res['RemoteServices'].pop()
        assert service['Service'] == srvname
        assert service['ApiEndpoint'] == srvendpoint

        entry = await iclient.core.add_bytes(b'ABCD')

        # Try a remote pin (will fail, token does not exist)
        with pytest.raises(aioipfs.PinRemoteError):
            res = await iclient.pin.remote.add(
                srvname,
                f'/ipfs/{entry["Hash"]}'
            )

        with pytest.raises(aioipfs.PinRemoteError):
            async for entry in iclient.pin.remote.ls(
                srvname,
                status=['queued']
            ):
                print(entry)

        await iclient.pin.remote.service.rm(srvname)
        res = await iclient.pin.remote.service.ls()
        assert len(res['RemoteServices']) == 0


class TestMultipart:
    def test_dirlisting(self, dir_hierarchy2):
        def find(name: str, data):
            for entry in data:
                _name, _fd, _ctype = entry[1]
                if _name == f'{dir_hierarchy2.name}/{name}':
                    return entry

        names = DirectoryListing(str(dir_hierarchy2), hidden=True).genNames()

        assert find('README.txt', names)
        assert find('README2.txt', names)
        assert find('d/.e/f/.file3', names)
        assert find('a/b/.c', names)
        assert find('.file2', names)

        names = DirectoryListing(str(dir_hierarchy2), hidden=False).genNames()

        assert find('.file2', names) is None
