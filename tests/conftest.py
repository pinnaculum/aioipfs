import pytest

import tempfile
import random
import time
import subprocess
import os
import os.path
import json
import tarfile

from distutils.version import StrictVersion
from pathlib import Path

import aioipfs

from aioipfs import util


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
def ipfs_version():
    p = subprocess.Popen(['ipfs', 'version'],
                         stdout=subprocess.PIPE)
    stdout, _ = p.communicate()
    return StrictVersion(stdout.decode().replace('ipfs version ', ''))


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

    yield tmpdir, apiport, sp

    time.sleep(0.5)
    # Cleanup
    sp.terminate()


apiport_a = 9011
gwport_a = 9090
swarmport_a = 9012


@pytest.fixture(scope='module')
def ipfsdaemon_with_auth():
    tmpdir = tempfile.mkdtemp()

    os.putenv('IPFS_PATH', tmpdir)
    os.system('ipfs init -e')

    cfg = ipfs_config_get()

    with tempfile.NamedTemporaryFile(mode='wt', delete=False) as ncfgf:
        cfg.Addresses.API = [
            f'/ip4/127.0.0.1/tcp/{apiport_a}',
            f'/ip6/::1/tcp/{apiport_a}',
        ]

        cfg.Addresses.Gateway = f'/ip4/127.0.0.1/tcp/{gwport_a}'
        cfg.Addresses.Swarm = [f"/ip4/127.0.0.1/tcp/{swarmport_a}"]

        # Empty bootstrap so we're not bothered
        cfg.Bootstrap = []

        cfg.Experimental.Libp2pStreamMounting = True
        cfg.Experimental.FilestoreEnabled = True

        cfg.API.Authorizations = {
            'Alice': {
                "AuthSecret": "basic:alice:password123",
                "AllowedPaths": ["/api/v0/files"]
            },
            'John': {
                "AuthSecret": "basic:john:12345",
                "AllowedPaths": ["/api/v0/add"]
            },
            'Bear': {
                "AuthSecret": "bearer:token123",
                "AllowedPaths": ["/api/v0"]
            }
        }

        cfg.write(ncfgf)

    ipfs_config_replace(ncfgf.name)

    sp = subprocess.Popen(['ipfs', 'daemon'], stdout=subprocess.PIPE)
    time.sleep(1)

    yield tmpdir, apiport_a, sp

    time.sleep(0.5)
    sp.terminate()


@pytest.fixture
def ipfs_peerid(ipfsdaemon):
    return ipfs_getconfig_var('Identity.PeerID').strip()


@pytest.fixture(autouse=True)
async def iclient(event_loop):
    client = aioipfs.AsyncIPFS(port=apiport, loop=event_loop)
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def iclient_with_auth(event_loop):
    client = aioipfs.AsyncIPFS(port=apiport_a, loop=event_loop)
    yield client
    await client.close()
