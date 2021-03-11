class IPFSConnectionError(Exception):
    pass


class APIError(Exception):
    """
    IPFS API error

    :param int code: IPFS error code
    :param str message: Error message
    """

    def __init__(self, code=-1, message='', http_status=-1):
        self.code = code
        self.message = message
        self.http_status = http_status


class UnknownAPIError(APIError):
    pass
