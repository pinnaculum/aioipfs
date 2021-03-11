from aioipfs.apis import SubAPI
from aioipfs.helpers import *  # noqa


class PinRemoteServiceAPI(SubAPI):
    async def add(self, service, endpoint, key):
        return await self.fetch_json(
            self.url('pin/remote/service/add'),
            params=quote_args(service, endpoint, key))

    async def ls(self, stat=False):
        params = {
            'stat': boolarg(stat)
        }

        return await self.fetch_json(self.url('pin/remote/service/ls'),
                                     params=params)

    async def rm(self, service):
        return await self.fetch_json(
            self.url('pin/remote/service/rm'),
            params=quote_args(service))


class PinRemoteAPI(SubAPI):
    def __init__(self, driver):
        super().__init__(driver)

        self.service = PinRemoteServiceAPI(driver)

    async def add(self,
                  service: str, objPath: str,
                  name=None,
                  background=False):
        params = {
            'service': service,
            ARG_PARAM: objPath,
            'background': boolarg(background)
        }

        if isinstance(name, str):
            params['name'] = name

        return await self.fetch_json(
            self.url('pin/remote/add'),
            params=params
        )

    async def ls(self, service: str,
                 name=None,
                 cid: list = [],
                 status: list = ['pinned']):
        params = {
            'service': service,
            'status': status
        }

        if len(cid) > 0:
            params['cid'] = cid

        if isinstance(name, str):
            params['name'] = name

        async for entry in self.mjson_decode(
                self.url('pin/remote/ls'),
                params=quote_dict(params)):
            yield entry

    async def rm(self, service: str,
                 name=None,
                 cid: list = [],
                 status: list = ['pinned'],
                 force=False):
        params = {
            'service': service,
            'status': status,
            'force': boolarg(force)
        }

        if len(cid) > 0:
            params['cid'] = cid

        if isinstance(name, str):
            params['name'] = name

        return await self.fetch_json(self.url('pin/remote/rm'),
                                     params=quote_dict(params))


class PinAPI(SubAPI):
    def __init__(self, driver):
        super().__init__(driver)

        self.remote = PinRemoteAPI(driver)

    async def add(self, multihash, recursive=True, progress=True):
        """
        Pin objects to local storage.
        """

        # We request progress status by default
        params = {
            ARG_PARAM: multihash,
            'recursive': boolarg(recursive),
            'progress': boolarg(progress)
        }

        async for added in self.mjson_decode(
                self.url('pin/add'), params=params):
            yield added

    async def ls(self, multihash=None, pintype='all', quiet=False):
        """
        List objects pinned to local storage.
        """

        params = {
            'type': pintype,
            'quiet': boolarg(quiet)
        }
        if multihash:
            params[ARG_PARAM] = multihash

        return await self.fetch_json(self.url('pin/ls'),
                                     params=params)

    async def rm(self, multihash, recursive=True):
        """
        Remove pinned objects from local storage.
        """

        params = {
            ARG_PARAM: multihash,
            'recursive': boolarg(recursive)
        }
        return await self.fetch_json(self.url('pin/rm'),
                                     params=params)

    async def verify(self, verbose=False, quiet=True):
        """
        Verify that recursive pins are complete.
        """

        params = {
            'verbose': boolarg(verbose),
            'quiet': boolarg(quiet)
        }
        return await self.fetch_json(self.url('pin/verify'),
                                     params=params)

    async def update(self, old, new, unpin=True):
        """
        Update a recursive pin

        :param str old: Path to old object
        :param str new: Path to new object
        :param bool unpin: Remove the old pin
        """

        params = quote_dict({
            ARG_PARAM: [old, new],
            'unpin': boolarg(unpin)
        })
        return await self.fetch_json(self.url('pin/update'), params=params)
