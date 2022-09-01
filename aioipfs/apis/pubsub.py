import io
import multibase
import sys
import asyncio
from typing import Optional

from aiohttp import payload
from aioipfs import multi
from aioipfs.api import SubAPI
from aioipfs.api import ARG_PARAM
from aioipfs.api import boolarg


class PubSubAPI(SubAPI):
    async def ls(self):
        """
        List the names of the subscribed pubsub topics.
        """
        return await self.fetch_json(self.url('pubsub/ls'))

    async def peers(self, topic=None):
        """
        List peers communicating over pubsub with this node.
        """

        params = {}
        if isinstance(topic, str):
            params[ARG_PARAM] = topic

        return await self.fetch_json(
            self.url('pubsub/peers'), params=params)

    async def pub(self, topic, data: Optional[str]):
        """
        Publish a message to a given pubsub topic.

        :param str topic: topic to publish the message to
        :param str data: message data
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

    async def sub(self, topic, discover=True, timeout=None, read_timeout=None):
        """
        Subscribe to messages on a given topic.

        This is an async generator yielding messages as they are read on the
        pubsub topic.

        :param str topic: topic to subscribe to
        :param bool discover: try to discover other peers subscribed to
            the same topic
        """

        params = {
            ARG_PARAM: multibase.encode('base64url', topic).decode(),
            'discover': boolarg(discover),
            'stream-channels': boolarg(True)
        }

        async for message in self.mjson_decode(
                self.url('pubsub/sub'),
                method='post',
                headers={'Connection': 'Close'},
                new_session=True,
                timeout=timeout if timeout else 60.0 * 60 * 24 * 8,
                read_timeout=read_timeout if read_timeout else 0,
                params=params):
            try:
                converted = self.decode_message(message)
            except Exception as e:
                print(f'Could not decode pubsub message ({topic}): {e}',
                      file=sys.stderr)
            else:
                yield converted

            await asyncio.sleep(0)

    def decode_message(self, psmsg):
        """
        Starting with go-ipfs v0.11, JSON fields in the pubsub messages
        are simply multibase-encoded (except the 'from' field which
        represents the PeerID)
        """

        conv_msg = {}
        conv_msg['from'] = psmsg['from']
        conv_msg['data'] = multibase.decode(psmsg['data'])
        conv_msg['seqno'] = multibase.decode(psmsg['seqno'])
        conv_msg['topicIDs'] = [multibase.decode(topic).decode() for topic in
                                psmsg['topicIDs']]
        return conv_msg
