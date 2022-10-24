import json
import asyncio
import sys

from aiohttp.web_exceptions import (HTTPInternalServerError,
                                    HTTPForbidden,
                                    HTTPNotFound,
                                    HTTPMethodNotAllowed,
                                    HTTPBadRequest)
from aiohttp.client_exceptions import *  # noqa

from aioipfs.helpers import *  # noqa
from aioipfs.exceptions import *  # noqa


DEFAULT_TIMEOUT = 60 * 60

HTTP_ERROR_CODES = [
    HTTPInternalServerError.status_code,
    HTTPBadRequest.status_code,
    HTTPForbidden.status_code,
    HTTPNotFound.status_code,
    HTTPMethodNotAllowed.status_code
]


class SubAPI:
    """
    Master class for all classes implementing API functions

    :param driver: the AsyncIPFS instance
    """

    def __init__(self, driver):
        self.driver = driver

    def url(self, path):
        return self.driver.api_endpoint(path)

    def decode_error(self, errormsg):
        """
        Decode a (JSON) error message from the daemon and
        return a tuple (text_message, error_code)
        """
        try:
            decoded_json = json.loads(errormsg)
            mtype = decoded_json.get('Type')
            assert mtype.lower() == 'error'
            return decoded_json['Message'], decoded_json['Code']
        except Exception:
            return None, None

    def handle_error(self, response, data):
        """
        When the daemon returns an HTTP status code != 200, this
        method is called to raise an API exception.
        """

        if response.status == HTTPNotFound.status_code:
            # 404
            raise EndpointNotFoundError(
                f'Endpoint for URL: {response.url} NOT FOUND'
            )

        msg, code = self.decode_error(data)

        if isinstance(msg, str) and code is not None:
            # Check for specific errors

            for errclass in [NotPinnedError,
                             InvalidCIDError,
                             NoSuchLinkError,
                             IpnsKeyError,
                             PinRemoteError]:
                if errclass.match(msg) is True:
                    raise errclass(
                        code=code,
                        message=msg,
                        http_status=response.status
                    )

            # Otherwise raise a generic error
            raise APIError(code=code,
                           message=msg,
                           http_status=response.status)
        else:
            raise UnknownAPIError()

    async def fetch_text(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.post(url, params=params) as response:
            status, textdata = response.status, await response.text()
            if status in HTTP_ERROR_CODES:
                self.handle_error(response, textdata)

            return textdata

    async def fetch_raw(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.post(url, params=params) as response:
            status, data = response.status, await response.read()
            if status in HTTP_ERROR_CODES:
                self.handle_error(response, data)

            return data

    async def fetch_json(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        return await self.post(url, params=params, outformat='json')

    async def post(self, url, data=None, headers={}, params={},
                   outformat='text'):
        try:
            async with self.driver.session.post(url, data=data,
                                                headers=headers,
                                                params=params) as response:
                if response.status in HTTP_ERROR_CODES:
                    return self.handle_error(
                        response, await response.read()
                    )

                if outformat == 'text':
                    return await response.text()
                elif outformat == 'json':
                    return await response.json()
                elif outformat == 'raw':
                    return await response.read()
                else:
                    raise Exception(
                        f'Unknown output format {outformat}')
        except (APIError, UnknownAPIError) as apierr:
            if self.driver.debug:
                print(f'{url}: Post API error: {apierr}',
                      file=sys.stderr)

            raise apierr
        except (ClientPayloadError,
                ClientConnectorError,
                ServerDisconnectedError,
                BaseException) as err:
            if self.driver.debug:
                print(f'{url}: aiohttp error: {err}',
                      file=sys.stderr)

            return None

    async def mjson_decode(self, url, method='post', data=None,
                           params=None, headers=None,
                           new_session=False,
                           timeout=60.0 * 60,
                           read_timeout=60.0 * 10):
        """
        Multiple JSON objects response decoder (async generator), used for
        the API endpoints which return multiple JSON messages

        :param str method: http method, get or post
        :param data: data, for POST only
        :param params: http params
        """

        kwargs = {'params': params if params else {}}

        if new_session is True:
            session = self.driver.get_session(
                conn_timeout=timeout,
                read_timeout=read_timeout
            )
        else:
            session = self.driver.session

        if method not in ['get', 'post']:
            raise ValueError('mjson_decode: unknown method')

        if method == 'post':
            if data is not None:
                kwargs['data'] = data

        if isinstance(headers, dict):
            kwargs['headers'] = headers

        try:
            async with getattr(session, method)(url, **kwargs) as response:
                async for raw_message in response.content:
                    message = decode_json(raw_message)

                    if message is not None:
                        if 'Message' in message and 'Code' in message:
                            self.handle_error(response, raw_message)
                        else:
                            yield message

                    await asyncio.sleep(0)
        except (asyncio.CancelledError,
                asyncio.TimeoutError) as err:
            if new_session is True:
                await session.close()

            raise err
        except APIError as e:
            if new_session is True:
                await session.close()

            raise e
        except (ClientPayloadError,
                ClientConnectorError,
                ServerDisconnectedError,
                Exception):
            if new_session is True:
                await session.close()

            raise IPFSConnectionError('Connection/payload error')

        if new_session is True:
            await session.close()
