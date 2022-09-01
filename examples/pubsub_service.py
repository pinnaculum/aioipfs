#!/usr/bin/env python
#
# Example of a pubsub service with aioipfs
#

import aioipfs
import asyncio


async def serve(topic):
    async with aioipfs.AsyncIPFS() as cli:
        try:
            async for message in cli.pubsub.sub(topic):
                print('Received message', message['data'], 'from',
                      message['from'])
                await cli.pubsub.pub('othertopic', 'Cool')
        except aioipfs.APIError as e:
            print(e.message)
        except Exception as e:
            print(e)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(serve('echo'))
