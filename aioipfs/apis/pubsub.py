import io
import asyncio
from typing import Union

import base58
import base64
import multibase

from aiohttp import payload
from aioipfs import multi
from aioipfs.helpers import quote_args
from aioipfs.api import SubAPI
from aioipfs.api import ARG_PARAM
from aioipfs.api import boolarg
from aioipfs.exceptions import InvalidPubMessageError


class PubSubAPI(SubAPI):
    async def ls(self):
        """
        List the names of the subscribed pubsub topics.

        :rtype dict:
        """

        api_post011 = await self.driver.agent_version_post011()

        reply = await self.fetch_json(self.url('pubsub/ls'))

        if not isinstance(reply, dict) or 'Strings' not in reply:
            return None

        if api_post011:
            # Do the multibase decoding of the topics list
            return {
                'Strings': [multibase.decode(topic).decode() for topic in
                            reply['Strings']]
            }
        else:
            return reply

    async def peers(self, topic=None):
        """
        List peers communicating over pubsub with this node.
        """

        params = {}
        if isinstance(topic, str):
            params[ARG_PARAM] = topic

        return await self.fetch_json(
            self.url('pubsub/peers'), params=params)

    async def pub(self, topic, data: Union[str, bytes]):
        """
        Publish a message to a given pubsub topic.

        :param str topic: topic to publish the message to
        :param data: message data (bytes or str)
        """

        api_post011 = await self.driver.agent_version_post011()

        if type(data) not in [str, bytes]:
            raise ValueError(
                'Invalid data type (should be bytes or str)'
            )

        if api_post011:
            return await self.__pub_multibase(topic, data)
        else:
            return await self.__pub_old(topic, data)

    async def __pub_old(self, topic, data: Union[str, bytes]):
        """
        Old publish wire format (pre 0.11.0)
        """

        msgd = data.decode() if isinstance(data, bytes) else data

        return await self.post(self.url('pubsub/pub'),
                               None, params=quote_args(topic, msgd))

    async def __pub_multibase(self, topic, data: Union[str, bytes]):
        """
        New publish wire format (post 0.11.0)
        """
        params = {
            ARG_PARAM: multibase.encode('base64url', topic).decode()
        }

        with multi.FormDataWriter() as mpwriter:
            if isinstance(data, str):
                part = payload.StringIOPayload(io.StringIO(data))
            elif isinstance(data, bytes):
                part = payload.BytesIOPayload(io.BytesIO(data))

            part.set_content_disposition('form-data', name='file')
            mpwriter.append_payload(part)

            return await self.post(self.url('pubsub/pub'), mpwriter,
                                   params=params, outformat='text')

    async def sub(self,
                  topic: str,
                  discover: bool = True,
                  timeout: int = None,
                  read_timeout: int = None):
        """
        Subscribe to messages on a given topic.

        This is an async generator yielding messages as they are read on the
        pubsub topic.

        :param str topic: topic to subscribe to
        :param bool discover: try to discover other peers subscribed to
            the same topic
        :param int timeout: global coroutine timeout
        :param int read_timeout: read timeout (between each message read)
        """

        api_post011 = await self.driver.agent_version_post011()

        params = {
            'discover': boolarg(discover),
            'stream-channels': boolarg(True)
        }

        if api_post011:
            # post v0.11.0: topic is encoded with multibase
            params[ARG_PARAM] = multibase.encode(
                'base64url', topic).decode()
        else:
            # pre v0.11.0: topic is passed as a raw string
            params[ARG_PARAM] = topic

        async for message in self.mjson_decode(
                self.url('pubsub/sub'),
                method='post',
                headers={'Connection': 'Close'},
                new_session=True,
                timeout=timeout if timeout else 60.0 * 60 * 24 * 8,
                read_timeout=read_timeout if read_timeout else 0,
                params=params):
            try:
                if api_post011:
                    converted = self._decode_message(message)
                else:
                    converted = self._decode_message_base58(message)
            except Exception as e:
                raise InvalidPubMessageError(
                    f'Could not decode pubsub message '
                    f'on topic {topic}: {e}'
                )
            else:
                yield converted

            await asyncio.sleep(0)

    def _decode_message(self, psmsg):
        """
        Starting with go-ipfs v0.11, JSON fields in the pubsub messages
        are simply multibase-encoded (except the 'from' field which
        represents the PeerID)

        This is the wire format used by go-ipfs/kubo >= 0.11.0
        """

        conv_msg = {}
        conv_msg['from'] = psmsg['from']
        conv_msg['data'] = multibase.decode(psmsg['data'])
        conv_msg['seqno'] = multibase.decode(psmsg['seqno'])
        conv_msg['topicIDs'] = [multibase.decode(topic).decode() for topic in
                                psmsg['topicIDs']]
        return conv_msg

    def _decode_message_base58(self, psmsg):
        """
        Convert a raw pubsub message (with base64-encoded fields) to a
        readable form

        This is the wire format used by go-ipfs/kubo < 0.11.0
        """

        conv_msg = {}
        conv_msg['from'] = base58.b58encode(
            base64.b64decode(psmsg['from']))
        conv_msg['data'] = base64.b64decode(psmsg['data'])
        conv_msg['seqno'] = base64.b64decode(psmsg['seqno'])
        conv_msg['topicIDs'] = psmsg['topicIDs']
        return conv_msg
