import pytest

import tempfile
import random
import time
import subprocess
import os
import os.path
import json

import asyncio
import aioipfs


def ipfs_getconfig_var(var):
    sp_getconfig = subprocess.Popen(['ipfs', 'config',
                                     var], stdout=subprocess.PIPE)
    stdout, stderr = sp_getconfig.communicate()
    return stdout.decode()


@pytest.fixture
def smalltar():
    import tarfile
    tpath = tempfile.mkstemp()[1]
    tar = tarfile.open(tpath, 'w|')
    tar.add(__file__)
    tar.close()
    yield tar, tpath
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
    for i in range(0, 128):
        filep.write(str(r.randint(i, i * 2)))
    return filep


def ipfs_config(param, value):
    os.system('ipfs config {0} "{1}"'.format(param, value))


def ipfs_config_json(param, value):
    os.system('ipfs config --json {0} "{1}"'.format(
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
    ipfs_config('Addresses.API',
                '/ip4/127.0.0.1/tcp/{0}'.format(apiport))
    ipfs_config('Addresses.Gateway',
                '/ip4/127.0.0.1/tcp/{0}'.format(gwport))
    ipfs_config_json('Addresses.Swarm',
                     '["/ip4/127.0.0.1/tcp/{0}"]'.format(swarmport))

    # Empty bootstrap so we're not bothered
    ipfs_config_json('Bootstrap', '[]')
    ipfs_config_json('Experimental.Libp2pStreamMounting', 'true')
    ipfs_config_json('Experimental.FilestoreEnabled', 'true')

    # Run the daemon and wait a bit
    sp = subprocess.Popen(['ipfs', 'daemon'],
                          stdout=subprocess.PIPE)
    time.sleep(1)

    yield tmpdir, sp

    time.sleep(0.5)
    # Cleanup
    sp.terminate()


@pytest.fixture
def ipfs_peerid(ipfsdaemon):
    return ipfs_getconfig_var('Identity.PeerID').strip()


@pytest.fixture()
def iclient(event_loop):
    return aioipfs.AsyncIPFS(port=apiport, loop=event_loop)


class TestAsyncIPFS:
    @pytest.mark.asyncio
    async def test_basic(self, event_loop, ipfsdaemon, iclient):
        tmpdir, sp = ipfsdaemon
        await iclient.id()
        await iclient.version()
        await iclient.commands()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_bootstrap(self, event_loop, ipfsdaemon, iclient):
        tmpdir, sp = ipfsdaemon
        await iclient.bootstrap.list()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_swarm(self, event_loop, ipfsdaemon, iclient):
        await iclient.swarm.peers()
        await iclient.swarm.addrs()
        await iclient.swarm.addrs_local()
        await iclient.swarm.addrs_listen()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_refs(self, event_loop, ipfsdaemon, iclient):
        async for refobj in iclient.refs.local():
            assert 'Ref' in refobj
        await iclient.close()

    @pytest.mark.asyncio
    async def test_block1(self, event_loop, ipfsdaemon, iclient, testfile1):
        reply = await iclient.block.put(testfile1)
        data = await iclient.block.get(reply['Key'])
        assert data.decode() == testfile1.read()
        await iclient.close()

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
        await iclient.close()

    @pytest.mark.asyncio
    async def test_addtar(self, event_loop, ipfsdaemon, iclient,
                          tmpdir, smalltar):
        tar, tarpath = smalltar
        reply = await iclient.tar.add(tarpath)
        tarhash = reply['Hash']
        fetched = await iclient.tar.cat(tarhash)
        f = tmpdir.join('new.tar')
        f.write(fetched)
        await iclient.close()

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
        await iclient.close()

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

        await iclient.close()

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
        await iclient.close()

    @pytest.mark.asyncio
    async def test_diag(self, event_loop, ipfsdaemon, iclient, tmpdir):
        reply = await iclient.diag.sys()
        assert 'diskinfo' in reply
        await iclient.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'0123456789'])
    async def test_catoffset(self, event_loop, ipfsdaemon, iclient,
                             tmpdir, data):
        entry = await iclient.add_bytes(data)
        raw = await iclient.cat(entry['Hash'], offset=4)
        assert raw.decode() == '456789'
        raw = await iclient.cat(entry['Hash'], offset=2, length=3)
        assert raw.decode() == '234'
        await iclient.close()

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
        await iclient.close()

    @pytest.mark.asyncio
    async def test_pubsub(self, event_loop, ipfsdaemon, iclient):
        # because we don't have pubsub enabled in the daemon with
        # --enable-pubsub-experiment this should raise an exception
        with pytest.raises(aioipfs.APIError):
            await iclient.pubsub.ls()
            await iclient.pubsub.peers()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_stats(self, event_loop, ipfsdaemon, iclient):
        await iclient.stats.bw()
        await iclient.stats.bitswap()
        await iclient.stats.repo()
        await iclient.close()

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
        await iclient.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('keyname', ['key1'])
    @pytest.mark.parametrize('keysize', [2048, 4096])
    async def test_keys(self, event_loop, ipfsdaemon, iclient,
                        keyname, keysize):
        reply = await iclient.key.gen(keyname, size=keysize)
        assert reply['Name'] == keyname
        key_hash = reply['Id']

        reply = await iclient.key.list()
        # initial peer key + the one we just made
        assert len(reply['Keys']) == 2

        removed = await iclient.key.rm(keyname)
        assert removed['Keys'].pop()['Id'] == key_hash
        await iclient.close()

    @pytest.mark.asyncio
    async def test_bitswap(self, event_loop, ipfsdaemon, iclient):
        await iclient.bitswap.wantlist()
        stats = await iclient.bitswap.stat()
        assert 'Wantlist' in stats
        assert 'DataSent' in stats
        await iclient.close()

    @pytest.mark.asyncio
    async def test_filestore(self, event_loop, ipfsdaemon, iclient):
        await iclient.filestore.dups()
        await iclient.close()

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
        await iclient.close()

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

        dag = await iclient.object.get(r2['Hash'])
        assert len(dag['Links']) == 2
        data1 = await iclient.cat(dag['Links'][0]['Hash'])
        data2 = await iclient.cat(dag['Links'][1]['Hash'])

        assert data1 == obj1
        assert data2 == obj2

        with pytest.raises(aioipfs.APIError):
            await iclient.object.patch.rm_link(obj['Hash'], 'obj1')

        rm = await iclient.object.patch.rm_link(r2['Hash'], 'obj1')
        dag = await iclient.object.get(rm['Hash'])
        assert len(dag['Links']) == 1
        await iclient.close()

    @pytest.mark.asyncio
    async def test_config(self, event_loop, ipfsdaemon, iclient, tmpdir):
        reply = await iclient.config.show()
        conf = json.loads(reply)
        assert 'API' in conf
        sameconf = tmpdir.join('config.json')
        sameconf.write(reply)
        await iclient.config.replace(str(sameconf))
        await iclient.close()

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
        await iclient.close()
