from aioipfs.api import SubAPI
from aioipfs.api import ARG_PARAM
from aioipfs.api import boolarg
from aioipfs import multi


class SwarmPeeringAPI(SubAPI):
    async def add(self, peer: str):
        """
        Add peers into the peering subsystem.

        :param str peer: address of peer to add into the peering subsystem
        """

        return await self.fetch_json(
            self.url('swarm/peering/add'),
            params={ARG_PARAM: peer}
        )

    async def ls(self):
        """
        List peers registered in the peering subsystem.
        """

        return await self.fetch_json(self.url('swarm/peering/ls'))

    async def rm(self, peer: str):
        """
        Remove a peer from the peering subsystem.

        :param str peer: ID of peer to remove from the peering subsystem
        """

        return await self.fetch_json(
            self.url('swarm/peering/rm'),
            params={ARG_PARAM: peer}
        )


class SwarmAPI(SubAPI):
    def __init__(self, driver):
        super().__init__(driver)

        self.peering = SwarmPeeringAPI(driver)

    async def peers(self, verbose=True, streams=False, latency=False,
                    direction=False):
        """
        List peers with open connections.

        :param bool verbose: display all extra information
        :param bool streams: Also list information about
            open streams for each peer
        :param bool latency: Also list information about
            latency to each peer
        :param bool direction: Also list information about
            the direction of connection
        """
        params = {
            'verbose': boolarg(verbose),
            'streams': boolarg(streams),
            'latency': boolarg(latency),
            'direction': boolarg(direction)
        }

        return await self.fetch_json(self.url('swarm/peers'), params=params)

    async def addrs(self):
        """
        List known addresses. Useful for debugging.
        """
        return await self.fetch_json(self.url('swarm/addrs'))

    async def addrs_local(self, id=False):
        """
        List local addresses.
        """
        params = {'id': boolarg(id)}
        return await self.fetch_json(self.url('swarm/addrs/local'),
                                     params=params)

    async def addrs_listen(self):
        """
        List interface listening addresses.
        """
        return await self.fetch_json(self.url('swarm/addrs/listen'))

    async def connect(self, peer):
        """
        Open connection to a given address.

        :param str peer: address of peer to connect to
        """
        params = {ARG_PARAM: peer}
        return await self.fetch_json(self.url('swarm/connect'),
                                     params=params)

    async def disconnect(self, peer):
        """
        Close connection to a given address.

        :param str peer: address of peer to disconnect from
        """
        params = {ARG_PARAM: peer}
        return await self.fetch_json(self.url('swarm/disconnect'),
                                     params=params)

    async def filters_add(self, filter):
        """
        Add an address filter.

        :param str filter: Multiaddr to filter
        """
        params = {ARG_PARAM: filter}
        return await self.fetch_json(self.url('swarm/filters/add'),
                                     params=params)

    async def filters_rm(self, filter):
        """
        Remove an address filter.

        :param str filter: Multiaddr filter to remove
        """
        params = {ARG_PARAM: filter}
        return await self.fetch_json(self.url('swarm/filters/rm'),
                                     params=params)

    async def limit(self, filepath, scope: str):
        """
        Get or set resource limits for a scope

        :param str filepath: path to the (JSON) file containing the limits
        :param str scope: scope of the limit
        """
        params = {ARG_PARAM: scope}

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('swarm/limit'), mpwriter,
                                   params=params, outformat='json')

    async def stats(self, scope: str):
        """
        Report resource usage for a scope

        :param str scope: scope of the stat report
        """

        return await self.fetch_json(self.url('swarm/stats'),
                                     params={ARG_PARAM: scope})
