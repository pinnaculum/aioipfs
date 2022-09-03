import os.path
from aiohttp import payload

from aioipfs.api import SubAPI
from aioipfs.api import boolarg
from aioipfs.api import ARG_PARAM
from aioipfs import multi
from aioipfs import UnknownAPIError


class DagAPI(SubAPI):
    async def put(self, filename,
                  store_codec='dag-cbor', input_codec='dag-json',
                  hashfn='sha2-256', pin=True,
                  allow_big_block=False):
        """
        Add a DAG node to IPFS

        :param str filename: a path to the object to import
        :param str format: format to use for the object inside IPFS
        :param str input_enc: object input encoding
        :param bool pin: pin the object after adding (default is False)
        :param bool offline: Offline mode (no announce)
        """

        if not os.path.isfile(filename):
            raise Exception('dag put: {} file does not exist'.format(filename))

        params = {
            'store-codec': store_codec,
            'hash': hashfn,
            'input-codec': input_codec,
            'pin': boolarg(pin),
            'allow-big-block': boolarg(allow_big_block)
        }

        basename = os.path.basename(filename)
        with multi.FormDataWriter() as mpwriter:
            dag_payload = payload.BytesIOPayload(open(filename, 'rb'))
            dag_payload.set_content_disposition('form-data',
                                                filename=basename)
            mpwriter.append_payload(dag_payload)

            return await self.post(self.url('dag/put'), mpwriter,
                                   params=params, outformat='json')

    async def car_export(self, cid, progress=False):
        """
        Streams the selected DAG as a .car stream on stdout.

        :param str cid: CID of a root to recursively export
        """

        return await self.fetch_raw(
            self.url('dag/export'),
            params={ARG_PARAM: cid, 'progress': boolarg(progress)}
        )

    async def get(self, objpath, output_codec=None):
        """
        Get a DAG node from IPFS

        :param str objpath: path of the object to fetch
        :param str output_codec: Format that the object will be encoded as
        """

        params = {ARG_PARAM: objpath}

        if isinstance(output_codec, str):
            params['output-codec'] = output_codec

        return await self.fetch_text(self.url('dag/get'),
                                     params=params)

    async def stat(self, cid, progress=True):
        """
        Gets stats for a DAG

        :param str cid: CID of a DAG root to get statistics for
        """

        params = {
            ARG_PARAM: cid,
            'progress': boolarg(progress)
        }

        async for value in self.mjson_decode(self.url('dag/stat'),
                                             params=params):
            yield value

    async def car_import(self, car, silent=False, pin_roots=True,
                         stats=False, allow_big_block=False):
        """
        Import the contents of .car files

        :param car: path to a .car archive or bytes object
        :param bool silent: No output
        :param bool pin_roots: Pin optional roots listed in the
            .car headers after importing
        """

        params = {
            'silent': boolarg(silent),
            'pin-roots': boolarg(pin_roots),
            'allow-big-block': boolarg(allow_big_block),
            'stats': boolarg(stats)
        }

        # Build the multipart form for the CAR import
        with multi.FormDataWriter() as mpwriter:
            if isinstance(car, str):
                if not os.path.isfile(car):
                    raise Exception('CAR file does not exist')

                basename = os.path.basename(car)
                car_payload = payload.BytesIOPayload(
                    open(car, 'rb'),
                    content_type='application/octet-stream'
                )

                car_payload.set_content_disposition('form-data',
                                                    name='file',
                                                    filename=basename)
            elif isinstance(car, bytes):
                car_payload = payload.BytesPayload(
                    car, content_type='application/octet-stream'
                )

                car_payload.set_content_disposition('form-data',
                                                    name='file',
                                                    filename='car')
            else:
                raise ValueError(
                    'Invalid parameter: argument should be '
                    'a bytes object or a path to a .car archive')

            mpwriter.append_payload(car_payload)

        if mpwriter.size == 0:
            raise UnknownAPIError('Multipart is empty')

        async with self.driver.session.post(
            self.url('dag/import'), data=mpwriter,
                params=params) as response:
            return await response.json()

    async def resolve(self, path):
        """
        Resolve an IPLD block

        :param str path: path to resolve
        """

        return await self.fetch_json(self.url('dag/resolve'),
                                     params={ARG_PARAM: path})
