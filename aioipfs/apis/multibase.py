from aioipfs.api import SubAPI
from aioipfs.api import boolarg
from aioipfs import multi


class MultibaseAPI(SubAPI):
    async def list(self, prefix=False, numeric=False):
        """
        List available multibase encodings
        """

        return await self.fetch_json(
            self.url('multibase/list'),
            params={
                'prefix': boolarg(prefix),
                'numeric': boolarg(numeric)
            }
        )

    async def decode(self, filepath: str):
        """
        Decode multibase string
        """

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('multibase/decode'),
                                   mpwriter, outformat='text')

    async def encode_transcode(self, method, filepath: str, base='base64url'):
        """
        Method used for encoding or transcoding
        """

        params = {
            'b': base
        }

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url(f'multibase/{method}'),
                                   mpwriter, params=params, outformat='text')

    async def encode(self, filepath: str, base='base64url'):
        return await self.encode_transcode('encode', filepath, base=base)

    async def transcode(self, filepath: str, base='base64url'):
        return await self.encode_transcode('transcode', filepath, base=base)
