
__version__ = '0.3.5'

from yarl import URL

import asyncio
import aiohttp

from aioipfs import api

class UnknownAPIError(Exception):
    pass

class APIError(Exception):
    """
    IPFS API error

    :param int code: IPFS error code
    :param str message: Error message
    """

    def __init__(self, code=-1, message='', http_status=-1):
        self.code = code
        self.message = message
        self.http_status = http_status

class AsyncIPFS(object):
    """
    Asynchronous IPFS API client

    :param str host: Hostname/IP of the IPFS daemon to connect to
    :param int port: The API port of the IPFS deamon
    :param int conns_max: Maximum HTTP connections for this client
        (default: 0)
    :param int conns_max_per_host: Maximum per-host HTTP connections
        (default: 0)
    :param int read_timeout: Socket read timeout
    """

    def __init__(self, host='localhost', port=5001, loop=None,
            conns_max=0, conns_max_per_host=0, read_timeout=None):

        self._conns_max = conns_max
        self._conns_max_per_host = conns_max_per_host
        self._read_timeout = read_timeout
        self._host = host
        self._port = port

        self.loop = loop if loop else asyncio.get_event_loop()

        self.api_url = URL.build(host=host, port=port,
                scheme='http', path='api/v0/')

        self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    limit=self._conns_max,
                    limit_per_host=self._conns_max_per_host,
                    loop=self.loop
                ), read_timeout=self._read_timeout)

        # Install the API handlers
        self.core = api.CoreAPI(self)
        self.p2p = api.P2PAPI(self)
        self.block = api.BlockAPI(self)
        self.pubsub = api.PubSubAPI(self)
        self.bitswap = api.BitswapAPI(self)
        self.bootstrap = api.BootstrapAPI(self)
        self.config = api.ConfigAPI(self)
        self.dag = api.DagAPI(self)
        self.dht = api.DhtAPI(self)
        self.diag = api.DiagAPI(self)
        self.files = api.FilesAPI(self)
        self.filestore = api.FilestoreAPI(self)
        self.key = api.KeyAPI(self)
        self.pin = api.PinAPI(self)
        self.log = api.LogAPI(self)
        self.name = api.NameAPI(self)
        self.object = api.ObjectAPI(self)
        self.refs = api.RefsAPI(self)
        self.repo = api.RepoAPI(self)
        self.swarm = api.SwarmAPI(self)
        self.tar = api.TarAPI(self)
        self.stats = api.StatsAPI(self)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def add(self):
        return self.core.add

    @property
    def add_bytes(self):
        return self.core.add_bytes

    @property
    def add_str(self):
        return self.core.add_str

    @property
    def add_json(self):
        return self.core.add_json

    @property
    def get(self):
        return self.core.get

    @property
    def id(self):
        return self.core.id

    @property
    def cat(self):
        return self.core.cat

    @property
    def dns(self):
        return self.core.dns

    @property
    def ls(self):
        return self.core.ls

    @property
    def ping(self):
        return self.core.ping

    @property
    def shutdown(self):
        return self.core.shutdown

    @property
    def version(self):
        return self.core.version

    @property
    def commands(self):
        return self.core.commands

    def api_endpoint(self, path):
        # Returns a joined URL between the base API url and path
        return self.api_url.join(URL(path))

    async def close(self):
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return
