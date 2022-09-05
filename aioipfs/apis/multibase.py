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

        :param str filepath: Path to the file containing the data to encode
        """

        with multi.FormDataWriter() as mpwriter:
            mpwriter.append_payload(multi.bytes_payload_from_file(filepath))

            return await self.post(self.url('multibase/decode'),
                                   mpwriter, outformat='text')

    async def __encode_transcode(self, method: str,
                                 filepath: str, base='base64url'):
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
        """
        Encode data into multibase string

        :param str filepath: Path to the file containing the data to encode
        :param str base: multibase encoding. Default: base64url
        """
        return await self.__encode_transcode('encode', filepath, base=base)

    async def transcode(self, filepath: str, base='base64url'):
        """
        Transcode multibase string between bases

        :param str filepath: Path to the file containing the data to transcode
        :param str base: multibase encoding. Default: base64url
        """
        return await self.__encode_transcode('transcode', filepath, base=base)
