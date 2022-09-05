from aioipfs.apis import SubAPI
from aioipfs.helpers import *  # noqa


class PinRemoteServiceAPI(SubAPI):
    async def add(self, service, endpoint, key):
        """
        Add remote pinning service.

        :param str service: Service name
        :param str endpoint: Service endpoint
        :param str key: Service key
        """
        return await self.fetch_json(
            self.url('pin/remote/service/add'),
            params=quote_args(service, endpoint, key))

    async def ls(self, stat=False):
        """
        List remote pinning services.

        :param bool stat: Try to fetch and display current pin count
            on remote service (queued/pinning/pinned/failed)
        """
        params = {
            'stat': boolarg(stat)
        }

        return await self.fetch_json(self.url('pin/remote/service/ls'),
                                     params=params)

    async def rm(self, service):
        """
        Remove remote pinning service.

        :param str service: Service name
        """
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
        """
        Pin object to remote pinning service.

        :param str service: Service name
        :param str objPath: Path to object(s) to be pinned
        :param str name: An optional name for the pin
        :param bool background: Add to the queue on the remote service
            and return immediately (does not wait for pinned status)
            Default: false
        """

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
        """
        List objects pinned to remote pinning service.

        :param str service: Name of the remote pinning service to use
        :param str name: Return pins with names that contain the value
            provided (case-sensitive, exact match)
        :param list cid: Return pins for the specified CIDs
        :param list status: Return pins with the specified statuses
            (queued,pinning,pinned,failed). Default: [pinned]
        """

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
        """
        Remove pins from remote pinning service.

        :param str service: Name of the remote pinning service to use
        :param str name: Return pins with names that contain the value
            provided (case-sensitive, exact match)
        :param list cid: Return pins for the specified CIDs
        :param list status: Return pins with the specified statuses
            (queued,pinning,pinned,failed). Default: [pinned]
        :param bool force: Allow removal of multiple pins matching the
            query without additional confirmation. Default: false
        """
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

    async def add(self, path, recursive=True, progress=True):
        """
        Pin objects to local storage.

        :param str path: Path to object(s) to be pinned
        :param bool recursive: Recursively pin the object linked to
            by the specified object(s)
        :param bool progress: Show progress
        """

        # We request progress status by default
        params = {
            ARG_PARAM: path,
            'recursive': boolarg(recursive),
            'progress': boolarg(progress)
        }

        async for added in self.mjson_decode(
                self.url('pin/add'), params=params):
            yield added

    async def ls(self, path=None, pintype='all', quiet=False,
                 stream: bool = False):
        """
        List objects pinned to local storage.

        :param str path: Path of object(s) to be listed
        :param str pintype: The type of pinned keys to list. Can be
            "direct", "indirect", "recursive", or "all"
        :param bool quiet: Write just hashes of objects
        :param bool stream: Enable streaming of pins as they are discovered
        """

        params = {
            'type': pintype,
            'quiet': boolarg(quiet),
            'stream': boolarg(stream)
        }
        if path:
            params[ARG_PARAM] = path

        return await self.fetch_json(self.url('pin/ls'),
                                     params=params)

    async def rm(self, path, recursive=True):
        """
        Remove pinned objects from local storage.

        :param str path: Path of object(s) to be removed
        :param bool recursive: Recursively unpin the object linked to
            by the specified object(s)
        """

        params = {
            ARG_PARAM: path,
            'recursive': boolarg(recursive)
        }
        return await self.fetch_json(self.url('pin/rm'),
                                     params=params)

    async def verify(self, verbose=False, quiet=True):
        """
        Verify that recursive pins are complete.

        :param bool verbose: Also write the hashes of non-broken pins
        :param bool quiet: Write just hashes of broken pins
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
        :param str new: Path to new object to be pinned
        :param bool unpin: Remove the old pin
        """

        params = quote_dict({
            ARG_PARAM: [old, new],
            'unpin': boolarg(unpin)
        })
        return await self.fetch_json(self.url('pin/update'), params=params)
