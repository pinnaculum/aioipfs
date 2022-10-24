import os.path

from yarl import URL
from multiaddr import Multiaddr

from aioipfs.api import SubAPI
from aioipfs.api import ARG_PARAM
from aioipfs.api import boolarg
from aioipfs.exceptions import APIError

from aioipfs.helpers import async_enterable
from aioipfs.helpers import maddr_tcp_explode
from aioipfs.helpers import quote_args
from aioipfs.helpers import quote_dict
from aioipfs.helpers import p2p_addr_explode


def protocol_format(proto: str, ns='x') -> str:
    if proto.startswith('/x/'):
        return proto

    return f'/{ns}/{proto}'


class TunnelDialerContext:
    """
    Service dial context manager
    """

    def __init__(self,
                 client,
                 peerId: str,
                 proto: str,
                 maddr: Multiaddr):
        self.client = client
        self.peerId = peerId
        self.protocol = proto
        self.maddr = maddr

    @property
    def maddr_port(self):
        """
        The connection TCP port
        """
        if self.maddr:
            return maddr_tcp_explode(self.maddr)[1]

    @property
    def maddr_host(self):
        """
        The connection hostname/ip
        """
        if self.maddr:
            return maddr_tcp_explode(self.maddr)[0]

    @property
    def failed(self):
        """
        Returns True if the service dial has failed
        """
        return self.maddr is None

    def httpUrl(self,
                path: str,
                query: str = '',
                fragment: str = '',
                scheme: str = 'http') -> URL:
        """
        Returns an HTTP URL targeting the remote P2P service
        associated with this context.

        :param str path: HTTP path
        :param str query: HTTP query
        :param str fragment: HTTP fragment
        :param str scheme: URL scheme (http or https)
        :rtype: URL
        """
        return URL.build(
            host=self.maddr_host,
            port=self.maddr_port,
            scheme=scheme,
            path=path,
            query=query,
            fragment=fragment
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        try:
            assert await self.client.p2p.listeners_for_listenaddr(
                self.maddr
            )
        except Exception:
            pass
        else:
            await self.client.p2p.listener_close(
                self.protocol,
                listen_address=str(self.maddr)
            )


class P2PDialerMixin:
    """
    APIs to help with dialing remote p2p services
    """

    @async_enterable
    async def dial_service(self,
                           peer: str,
                           protocol: str,
                           address=None,
                           auto=True,
                           allow_loopback=False):
        """
        Dial a remote IPFS p2p service.

        Returns an async context manager:

        async with client.p2p.dial_service(...) as ctx:
            print(ctx.maddr_host, ctx.maddr_port)

        :param str peer: Peer ID
        :param str protocol: Service protocol (e.g /x/helloworld)
        :param str address: Multiaddr for the connection
        :param bool auto: Automatically assign a multiaddr (only works
            if the kubo daemon is local)
        :param bool allow_loopback: Allow dialing a service on this node
        """
        if auto is True and not address and self.driver.host_local:
            address = self.driver.allocate_tcp_maddr()

        if await self.driver.agent_version_post0418():
            proto = protocol_format(protocol)
        else:
            proto = protocol

        return await self._dial_start(peer, proto, address,
                                      allow_loopback=allow_loopback)

    @async_enterable
    async def dial_endpoint(self,
                            p2pEndpointAddr: str,
                            address=None,
                            auto=True,
                            allow_loopback=False):
        """
        Dial a remote p2p service by passing an endpoint address.

        /p2p/12D3KooWAci7T5tA1ZaxBBREVEdLX5FJkH2GBcgbJGW6LqJtBgOp/x/hello

        Returns an async context manager:

        async with client.p2p.dial_endpoint('/p2p/...') as ctx:
            ...

        :param str p2pEndpointAddr: Endpoint address
        :param str address: Multiaddr for the connection
        :param bool auto: Automatically assign a multiaddr (only works
            if the kubo daemon is local)
        :param bool allow_loopback: Allow dialing a service on this node
        """

        if auto is True and not address and self.driver.host_local:
            address = self.driver.allocate_tcp_maddr()

        exploded = p2p_addr_explode(p2pEndpointAddr)

        if exploded:
            peerId, protoFull, pVersion = exploded

            return await self._dial_start(
                peerId, protoFull, str(address),
                allow_loopback=allow_loopback
            )
        else:
            raise ValueError(f'Invalid P2P service address: {p2pEndpointAddr}')

    async def _dial_start(self,
                          peer: str,
                          proto: str,
                          address: str,
                          allow_loopback=False):
        """
        Start the P2P dial and return a TunnelDialerContext
        """

        if not address:
            raise ValueError('No multiaddr provided')

        node_id = (await self.driver.core.id())['ID']

        if allow_loopback is True and node_id == peer:
            listeners = await self.listeners_for_proto(proto)

            for listener in listeners:
                # Return the first matching ListenAddress

                if listener['ListenAddress'] == f'/p2p/{node_id}':
                    return TunnelDialerContext(
                        self.driver, peer, proto,
                        Multiaddr(listener['TargetAddress'])
                    )

        try:
            peerAddr = os.path.join(
                '/ipfs', peer) if not peer.startswith('/ipfs/') else peer
            resp = await self.driver.p2p.dial(proto, address, peerAddr)

            if resp:
                maddr = Multiaddr(resp['Address'])
            elif isinstance(address, Multiaddr):
                maddr = address
            elif isinstance(address, str):
                maddr = Multiaddr(address)
        except Exception:
            return TunnelDialerContext(self.driver, peer, proto, None)

        return TunnelDialerContext(self.driver, peer, proto, maddr)

    async def streams_for_proto(self, protocol: str) -> list:
        return [stream for stream in await self.streams() if
                stream['Protocol'] == protocol]

    async def streams_for_targetaddr(self, addr: Multiaddr) -> list:
        return [stream for stream in await self.streams() if
                stream['TargetAddress'] == str(addr)]

    async def listeners_for_targetaddr(self, addr: Multiaddr) -> list:
        return [stream for stream in await self.listeners() if
                stream['TargetAddress'] == str(addr)]

    async def listeners_for_listenaddr(self, addr: Multiaddr) -> list:
        return [stream for stream in await self.listeners() if
                stream['ListenAddress'] == str(addr)]

    async def listeners_for_proto(self, protocol: str) -> list:
        return [stream for stream in await self.listeners() if
                stream['Protocol'] == protocol]

    async def listeners(self) -> list:
        try:
            resp = await self.ls(headers=True)
            assert isinstance(resp, dict)
            return resp['Listeners'] if resp['Listeners'] else []
        except (AssertionError, APIError):
            return []

    async def streams(self) -> list:
        try:
            resp = await self.stream_ls(headers=True)
            assert isinstance(resp, dict)
            return resp['Streams'] if resp['Streams'] else []
        except (AssertionError, APIError):
            return []


class P2PAPI(P2PDialerMixin, SubAPI):
    """
    P2P API.

    Note: go-ipfs v0.4.18 introduced some changes in the P2P subsystem
    and some endpoints were renamed. Agent version detection is done
    in the affected API calls to maintain compatibility.
    """
    async def listener_open(self, protocol, address,
                            allow_custom_protocol=False,
                            report_peerid=False):
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
                'allow-custom-protocol': boolarg(allow_custom_protocol),
                'report-peer-id': boolarg(report_peerid)
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
