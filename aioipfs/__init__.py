__version__ = '0.5.6'

from yarl import URL
from distutils.version import StrictVersion

import asyncio
import aiohttp
import re

from multiaddr import Multiaddr
from multiaddr.exceptions import ParseError
from multiaddr.exceptions import StringParseError

from aioipfs import api
from aioipfs.exceptions import *  # noqa
from aioipfs.apis import dag as dag_api
from aioipfs.apis import pin as pin_api
from aioipfs.apis import multibase as multibase_api
from aioipfs.apis import pubsub as pubsub_api


RPC_API_DEFAULT_PORT = 5001


class AsyncIPFS(object):
    """
    Asynchronous IPFS API client

    :param str maddr: The multiaddr for the IPFS daemon's RPC API
        (this is the preferred method of specifying the node's address)
    :param str host: Hostname/IP of the IPFS daemon to connect to
    :param int port: The API port of the IPFS deamon
    :param int conns_max: Maximum HTTP connections for this client
        (default: 0)
    :param int conns_max_per_host: Maximum per-host HTTP connections
        (default: 0)
    :param int read_timeout: Socket read timeout
    :param str api_version': IPFS protocol version ('v0' by default)
    :param bool debug: Enable client debugging traces
    :param loop: force a specific asyncio event loop
    """

    def __init__(self,
                 host='localhost',
                 port=RPC_API_DEFAULT_PORT,
                 maddr=None,
                 loop=None,
                 conns_max=0, conns_max_per_host=0,
                 read_timeout=0, api_version='v0',
                 debug=False):

        self._conns_max = conns_max
        self._conns_max_per_host = conns_max_per_host
        self._read_timeout = read_timeout
        self._debug = debug
        self._host, self._port = None, None
        self.loop = loop if loop else asyncio.get_event_loop()

        self._api_url = self.__compute_base_api_url(host=host,
                                                    port=port,
                                                    maddr=maddr,
                                                    api_version=api_version)

        self.session = self.get_session()

        # Install the API handlers
        self.core = api.CoreAPI(self)
        self.p2p = api.P2PAPI(self)
        self.block = api.BlockAPI(self)
        self.pubsub = pubsub_api.PubSubAPI(self)
        self.bitswap = api.BitswapAPI(self)
        self.bootstrap = api.BootstrapAPI(self)
        self.cid = api.CidAPI(self)
        self.config = api.ConfigAPI(self)
        self.dag = dag_api.DagAPI(self)
        self.dht = api.DhtAPI(self)
        self.diag = api.DiagAPI(self)
        self.file = api.FileAPI(self)
        self.files = api.FilesAPI(self)
        self.filestore = api.FilestoreAPI(self)
        self.key = api.KeyAPI(self)
        self.pin = pin_api.PinAPI(self)
        self.log = api.LogAPI(self)
        self.multibase = multibase_api.MultibaseAPI(self)
        self.name = api.NameAPI(self)
        self.object = api.ObjectAPI(self)
        self.refs = api.RefsAPI(self)
        self.repo = api.RepoAPI(self)
        self.routing = api.RoutingAPI(self)
        self.swarm = api.SwarmAPI(self)
        self.tar = api.TarAPI(self)
        self.stats = api.StatsAPI(self)

        self._agent_version = None

    @property
    def debug(self):
        return self._debug

    @property
    def agent_version(self):
        return self._agent_version

    @property
    def api_url(self):
        return self._api_url

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
    def getgen(self):
        return self.core.getgen

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

    def __compute_base_api_url(self, host=None, port=None,
                               maddr=None, api_version='v0'):
        """
        Compute and return the base kubo API url from the settings
        passed to the constructor. If a multiaddr is passed, use that
        to build the API URL, otherwise use host/port.

        :rtype: URL
        """

        if isinstance(maddr, str) or isinstance(maddr, Multiaddr):
            try:
                # The Multiaddr constructor can handle a string or
                # a Multiaddr instance
                node_maddr = Multiaddr(maddr)

                # Extract the host/port from the multiaddr protocols
                for proto in node_maddr.protocols():
                    if proto.name in ['ip4', 'ip6', 'dns4', 'dns6']:
                        self._host = node_maddr.value_for_protocol(
                            proto.name
                        )
                    elif proto.name == 'tcp':
                        self._port = int(
                            node_maddr.value_for_protocol(proto.name)
                        )

                assert isinstance(self._host, str)
                assert isinstance(self._port, int)
            except (StringParseError,
                    ParseError,
                    AssertionError) as perr:
                raise InvalidNodeAddressError(
                    f'Invalid kubo node multiaddr: {maddr}: {perr}'
                )
        elif isinstance(host, str) and isinstance(port, int):
            self._host = host
            self._port = port
        else:
            raise InvalidNodeAddressError()

        return URL.build(
            host=self._host,
            port=self._port,
            scheme='http',
            path=f'/api/{api_version}/'
        )

    def api_endpoint(self, path):
        # Returns a joined URL between the base API url and path
        return self.api_url.join(URL(path))

    async def close(self):
        await self.session.close()

    async def agent_version_get(self):
        if self.agent_version is None:
            node_idinfo = await self.core.id()

            if node_idinfo:
                agent_version = node_idinfo.get('AgentVersion')
                if not isinstance(agent_version, str):
                    raise ValueError('Invalid agent version')

                comps = agent_version.rstrip('/').split('/')

                if len(comps) >= 2:
                    self._agent_version = comps[1]

        return self.agent_version

    async def agent_version_superioreq(self, version):
        """
        Returns True if the node's agent version is superior or equal to
        version

        :param str version: a go-ipfs version number e.g 0.4.10
        """
        try:
            node_vs = await self.agent_version_get()
            node_vs = re.sub('(-.*$)', '', node_vs)
            version_node = StrictVersion(node_vs)
            version_ref = StrictVersion(version)
            return version_node >= version_ref
        except BaseException:
            return False

    async def agent_version_post0418(self):
        return await self.agent_version_superioreq('0.4.18')

    def get_session(self, conn_timeout=60.0 * 30, read_timeout=60.0 * 10):
        return aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=self._conns_max,
                limit_per_host=self._conns_max_per_host,
                loop=self.loop
            ), timeout=aiohttp.ClientTimeout(
                total=conn_timeout,
                sock_read=read_timeout
            )
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return
