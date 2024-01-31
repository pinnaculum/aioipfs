import json
from functools import reduce
from pathlib import Path

try:
    import ipfs_car_decoder as car_decoder
    have_car_decoder = True
except Exception:
    have_car_decoder = False
    car_decoder = None


class CARDecoderMissing(Exception):
    pass


def car_open(car_path: Path):
    """
    Open a Content-Addressable aRchive file and return the CAR stream.

    :param Path car_path: CAR file path
    """

    if not have_car_decoder:
        raise CARDecoderMissing()

    return car_decoder.FileByteStream(car_path)


async def car_bytes(stream, cid: str) -> bytes:
    """
    CAR stream to bytes

    :param stream: CAR stream
    :param str cid: CID of the UnixFS file to export
    :rtype: bytes
    """

    buff = b''

    async for chunk in car_decoder.stream_bytes(cid, stream):
        buff += chunk

    return buff


class DotJSON(dict):
    """
    Based on edict, described here:

    https://gist.github.com/markhu/fbbab71359af00e527d0
    """

    __delattr__ = dict.__delitem__

    def __init__(self, data):
        if isinstance(data, str):
            data = json.loads(data)
        else:
            data = data

        for name, value in data.items():
            setattr(self, name, self._wrap(value))

    def _traverse(self, obj, attr):
        attrd = attr.replace('__', '-')
        if self._is_indexable(obj):
            try:
                return obj[int(attrd)]
            except:
                return None
        elif isinstance(obj, dict):
            return obj.get(attrd, None)
        else:
            return attrd

    def __getattr__(self, attr):
        if '.' in attr:
            attrVal = attr.split('.').replace('__', '-')
            return reduce(self._traverse, attrVal, self)
        return self.get(attr, None)

    def __setattr__(self, attr, value):
        attrd = attr.replace('__', '-')
        dict.__setitem__(self, attrd, value)

    def _wrap(self, value):
        if self._is_indexable(value):
            # (!) recursive (!)
            return type(value)([self._wrap(v) for v in value])
        elif isinstance(value, dict):
            return DotJSON(value)
        else:
            return value

    @staticmethod
    def _is_indexable(obj):
        return isinstance(obj, (tuple, list, set, frozenset))

    def write(self, fd):
        fd.write(json.dumps(self))
        fd.flush()
