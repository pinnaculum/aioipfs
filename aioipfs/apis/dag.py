import os.path
from pathlib import Path
from aiohttp import payload

from aioipfs.api import SubAPI
from aioipfs.api import boolarg
from aioipfs.api import ARG_PARAM
from aioipfs import multi
from aioipfs import UnknownAPIError
from aioipfs import util


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

    async def car_export(self, cid: str, progress: bool = False,
                         output_path: Path = None):
        """
        Streams the selected DAG as a .car stream and return it
        as a raw buffer or write it to a file if output_path is
        passed.

        :param str cid: Root CID of a DAG to recursively export
        :param bool progress: Stream progress
        :param Path output_path: Write the CAR data to this file (optional)
        """

        car_data = await self.fetch_raw(
            self.url('dag/export'),
            params={ARG_PARAM: cid, 'progress': boolarg(progress)}
        )

        if output_path is None:
            return car_data
        else:
            with open(output_path, 'wb') as car:
                car.write(car_data)

    export = car_export

    async def export_to_directory(self,
                                  cid: str,
                                  dst_dir: Path) -> bool:
        """
        Export a UnixFS DAG to a CAR and unpack it to a directory

        :param str cid: CID of a UnixFS DAG to recursively export
        :param Path dst_dir: Filesystem destination path
        :rtype: bool
        """

        if not util.have_car_decoder:
            raise util.CARDecoderMissing(
                'The CAR decoding library is not available')

        if not dst_dir.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)

        stream = await self.car_stream(
            self.url('dag/export'),
            params={ARG_PARAM: cid, 'progress': boolarg(False)}
        )

        if not stream:
            raise ValueError(f'Failed to get car stream for {cid}')

        await util.car_decoder.write_car_filesystem_to_path(
            cid, stream, str(dst_dir)
        )

        return True

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
