import orjson
import sys

from urllib.parse import quote

ARG_PARAM = 'arg'


def boolarg(arg):
    return str(arg).lower()


def quote_args(*args):
    # Used in the few cases where there are multiple 'arg=' URL params
    # that yarl can't handle at the moment
    quoted = ''

    if len(args) > 0:
        for arg in args:
            quoted += '&{0}={1}'.format(ARG_PARAM, quote(str(arg)))
        return quoted[1:]


def quote_dict(data):
    quoted = ''

    if not isinstance(data, dict):
        raise ValueError('quote_dict: need dictionary')

    for arg, value in data.items():
        if isinstance(value, list):
            for lvalue in value:
                quoted += '&{0}={1}'.format(arg, quote(str(lvalue)))
        elif isinstance(value, str):
            quoted += '&{0}={1}'.format(arg, quote(value))
        elif isinstance(value, int):
            quoted += '&{0}={1}'.format(arg, quote(str(value)))
        elif isinstance(value, bool):
            quoted += '&{0}={1}'.format(arg, quote(boolarg(value)))

    if len(quoted) > 0:
        return quoted[1:]


def decode_json(data):
    if not data:
        return None
    try:
        json_obj = orjson.loads(data.decode())
    except Exception as exc:
        print(data, file=sys.stderr)
        print('Could not read JSON object:', str(exc), file=sys.stderr)
        return None

    return json_obj
