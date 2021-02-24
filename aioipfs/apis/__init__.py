import json
import asyncio

from aiohttp.web_exceptions import (HTTPError,
                                    HTTPInternalServerError,
                                    HTTPServerError, HTTPBadRequest)

from aioipfs.helpers import *  # noqa
from aioipfs.exceptions import *  # noqa


DEFAULT_TIMEOUT = 60 * 60

HTTP_ERROR_CODES = [
    HTTPInternalServerError.status_code,
    HTTPBadRequest.status_code,
    HTTPError.status_code,
    HTTPServerError.status_code
]


class SubAPI(object):
    """
    Master class for all classes implementing API functions

    :param driver: the AsyncIPFS instance
    """

    def __init__(self, driver):
        self.driver = driver

    def url(self, path):
        return self.driver.api_endpoint(path)

    def decode_error(self, errormsg):
        try:
            decoded_json = json.loads(errormsg)
            msg = decoded_json['Message']
            code = decoded_json['Code']
            return msg, code
        except Exception:
            return None, None

    async def fetch_text(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.post(url, params=params) as response:
            status, textdata = response.status, await response.text()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(textdata)
                raise APIError(code=code, message=msg,
                               http_status=status)
            return textdata

    async def fetch_raw(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.post(url, params=params) as response:
            status, data = response.status, await response.read()
            if status in HTTP_ERROR_CODES:
                msg, code = self.decode_error(data)
                raise APIError(code=code, message=msg,
                               http_status=status)
            return data

    async def fetch_json(self, url, params={}, timeout=DEFAULT_TIMEOUT):
        async with self.driver.session.post(url, params=params) as response:
            status, jsondata = response.status, await response.json()
            if status in HTTP_ERROR_CODES:
                if 'Message' in jsondata and 'Code' in jsondata:
                    raise APIError(
                        code=jsondata['Code'],
                        message=jsondata['Message'],
                        http_status=status)
                else:
                    raise UnknownAPIError()

            return jsondata

    async def post(self, url, data, headers={}, params={},
                   timeout=DEFAULT_TIMEOUT, outformat='text'):
        async with self.driver.session.post(url, data=data,
                                            headers=headers,
                                            params=params) as response:
            if response.status in HTTP_ERROR_CODES:
                errtext = await response.read()
                raise APIError(message=errtext,
                               http_status=response.status)

            if outformat == 'text':
                return await response.text()
            elif outformat == 'json':
                return await response.json()
            else:
                raise Exception('Unknown output format {0}'.format(outformat))

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

        kwargs = {'params': params if isinstance(params, dict) else {}}

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
                            raise APIError(code=message['Code'],
                                           message=message['Message'],
                                           http_status=response.status)
                        else:
                            yield message

                    await asyncio.sleep(0)
        except asyncio.CancelledError as err:
            if new_session is True:
                await session.close()

            raise err

        if new_session is True:
            await session.close()
