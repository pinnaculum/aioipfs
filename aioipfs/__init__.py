
__version__ = '0.3'

from yarl import URL, quoting

import asyncio
import aiohttp

from aioipfs import api

# Exceptions

class APIUnknownException(Exception):
    pass

class APIException(Exception):
    """ Generic exception raised from SubAPI.fetch_*() """

    def __init__(self, code, message):
        self.code = code
        self.message = message

class AsyncIPFS(object):
    ''' Asynchronous IPFS API client using aiohttp and aiofiles

    Parameters
    ----------
    host : str
        Hostname/IP  of the IPFS daemon to connect to
    port : int
        The API port of the IPFS deamon
    '''

    def __init__(self, host='localhost', port=5001, loop=None, **kwargs):
        self._conns_max = kwargs.get('conns_max', 8)
        self._conns_max_per_host = kwargs.get('conns_max_per_host', 4)
        self._read_timeout = kwargs.pop('read_timeout', None)

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

    # Make easy access to the 'core' api
    @property
    def add(self):
        return self.core.add

    @property
    def add_bytes(self):
        return self.core.add_bytes

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
