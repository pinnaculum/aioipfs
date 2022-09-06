import re


class InvalidNodeAddressError(Exception):
    pass


class IPFSConnectionError(Exception):
    pass


class APIError(Exception):
    """
    IPFS API error

    :param int code: IPFS error code
    :param str message: Error message
    :param int http_status: HTTP status code
    """

    def __init__(self, code=-1, message='', http_status=-1):
        self.code = code
        self.message = message
        self.http_status = http_status

    @classmethod
    def match(cls, message: str):
        """
        :param str message: Error message string returned by kubo
        :rtype: bool
        """
        return False


class EndpointNotFoundError(APIError):
    """
    Exception for when a RPC endpoint is not found (HTTP 404)
    """


class NotPinnedError(APIError):
    """
    Content not pinned or pinned indirectly
    """

    @classmethod
    def match(cls, message: str):
        return message.lower() == 'not pinned or pinned indirectly'


class InvalidCIDError(APIError):
    """
    Invalid CID or selected encoding not supported
    """

    @classmethod
    def match(cls, message: str):
        return message.lower().endswith(
            'invalid cid: selected encoding not supported'
        )


class NoSuchLinkError(APIError):
    """
    No link by that name
    """

    @classmethod
    def match(cls, message: str):
        return message == 'no link by that name'


class IpnsKeyError(APIError):
    """
    IPNS key errors
    """

    @classmethod
    def match(cls, message: str):
        ma = re.search(r'^key with name ([\'\\\w]+) already exists',
                       message)
        return ma is not None


class PinRemoteError(APIError):
    """
    Any kind of error ocurring when interacting with a
    remote pinning service.
    """

    @classmethod
    def match(cls, message: str):
        # TODO: match all types of remote pin errors
        return message.startswith(
            'empty response from remote pinning service'
        ) or message.startswith(
            'service endpoint must be a valid HTTP URL'
        ) or 'ERROR_UNRECOGNISED_TOKEN' in message or \
            "ERR_INVALID_TOKEN" in message


class UnknownAPIError(APIError):
    pass


class InvalidPubMessageError(Exception):
    """
    Invalid pubsub message encoding error
    """
