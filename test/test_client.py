
import pytest

import tempfile
import random
import time
import subprocess
import os, os.path
import json
import shutil

import asyncio, json
import aioipfs

def ipfs_getconfig_var(var):
    sp_getconfig = subprocess.Popen(['ipfs', 'config',
        var], stdout = subprocess.PIPE)
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
def randomfile(tmpdir):
    r = random.Random()
    filep = tmpdir.join('testfile2.txt')
    for i in range(0, 128):
        filep.write(str(r.randint(i, i*2)))
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
            stdout = subprocess.PIPE)
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
        peerid = await iclient.id()
        version = await iclient.version()
        commands = await iclient.commands()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_bootstrap(self, event_loop, ipfsdaemon, iclient):
        tmpdir, sp = ipfsdaemon
        boot = await iclient.bootstrap.list()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_swarm(self, event_loop, ipfsdaemon, iclient):
        peers = await iclient.swarm.peers()
        addrs = await iclient.swarm.addrs()
        addrs = await iclient.swarm.addrs_local()
        addrs = await iclient.swarm.addrs_listen()
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
            randomfile):
        count = 0
        async for added in iclient.add(str(testfile1)):
            count += 1
        assert count == 1
        count = 0
        all = [[ str(testfile1), str(randomfile)]]
        async for added in iclient.add(*all):
            count += 1
        assert count == 2

    @pytest.mark.asyncio
    async def test_addtar(self, event_loop, ipfsdaemon, iclient, tmpdir, smalltar):
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
    async def test_addjson(self, event_loop, ipfsdaemon, iclient, order, second):
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
        reply = await iclient.add_bytes(data)
        catD = await iclient.cat(reply['Hash'])
        assert catD == data
        await iclient.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('data', [b'234098dsfkj2doidf0'])
    async def test_dag(self, event_loop, ipfsdaemon, iclient, tmpdir, data):
        entry = await iclient.add_bytes(data)
        jsondag = {'dag': {'/': entry['Hash']}}
        filedag = tmpdir.join('jsondag.txt')
        filedag.write(json.dumps(jsondag))

        reply = await iclient.dag.put(filedag)
        path = os.path.join(reply['Cid']['/'], 'dag')
        raw = await iclient.cat(path)
        assert raw == data

        back = await iclient.dag.get(path)
        await iclient.close()

    @pytest.mark.asyncio
    async def test_diag(self, event_loop, ipfsdaemon, iclient, tmpdir):
        reply = await iclient.diag.sys()
        assert 'diskinfo' in reply
        await iclient.close()

    @pytest.mark.asyncio
    async def test_multiget(self, event_loop, ipfsdaemon,
            iclient, randomfile, tmpdir):
        hashes = []

        # Create 16 variations of randomfile and add them to the node
        for idx in range(0, 16):
            randomfile.write('ABCD' + str(idx))
            async for reply in iclient.add(str(randomfile)):
                hashes.append(reply['Hash'])

        # Get them all back concurrently
        tasks = [ iclient.get(hash, dstdir=tmpdir) for hash in hashes ]
        await asyncio.gather(*tasks)
        await iclient.close()

    @pytest.mark.asyncio
    async def test_pubsub(self, event_loop, ipfsdaemon, iclient):
        # because we don't have pubsub enabled in the daemon with
        # --enable-pubsub-experiment this should raise an exception
        with pytest.raises(aioipfs.APIError) as exc:
            topics = await iclient.pubsub.ls()
            peers  = await iclient.pubsub.peers()
        await iclient.close()

    @pytest.mark.asyncio
    async def test_stats(self, event_loop, ipfsdaemon, iclient):
        stats = await iclient.stats.bw()
        stats = await iclient.stats.bitswap()
        stats = await iclient.stats.repo()
        await iclient.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('protocol', ['test'])
    @pytest.mark.parametrize('address', ['/ip4/127.0.0.1/tcp/10000'])
    async def test_p2p(self, event_loop, ipfsdaemon, iclient, protocol,
            address):
        ret = await iclient.p2p.listener_open(protocol, address)
        listeners = await iclient.p2p.listener_ls(headers=True)
        assert len(listeners['Listeners']) > 0
        assert listeners['Listeners'][0]['Protocol'] == '/p2p/{}'.format(
                protocol)
        assert listeners['Listeners'][0]['Address'] == address
        await iclient.p2p.listener_close(protocol)
        listeners = await iclient.p2p.listener_ls()
        assert listeners['Listeners'] is None
        await iclient.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('keyname', ['key1'])
    async def test_keys(self, event_loop, ipfsdaemon, iclient, keyname):
        reply = await iclient.key.gen(keyname, size=2048)
        assert reply['Name'] == keyname
        key_hash = reply['Id']

        reply = await iclient.key.list()
        assert len(reply['Keys']) == 2 # initial peer key + the one we just made

        removed = await iclient.key.rm(keyname)
        assert removed['Keys'].pop()['Id'] == key_hash
        await iclient.close()

    @pytest.mark.asyncio
    async def test_bitswap(self, event_loop, ipfsdaemon, iclient):
        wlist = await iclient.bitswap.wantlist()
        stats = await iclient.bitswap.stat()
        assert 'Wantlist' in stats
        assert 'DataSent' in stats
        await iclient.close()

    @pytest.mark.asyncio
    async def test_filestore(self, event_loop, ipfsdaemon, iclient):
        dups = await iclient.filestore.dups()
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
