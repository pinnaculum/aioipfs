import pytest
from multiaddr import Multiaddr

from aioipfs.helpers import maddr_tcp_explode
from aioipfs.helpers import p2p_addr_explode
from aioipfs.helpers import peerid_reencode


class TestHelpers:
    def test_maddr_explode(self):
        assert maddr_tcp_explode(
            Multiaddr('/ip6/::1/tcp/3217')) == ('::1', 3217)

        assert maddr_tcp_explode(
            Multiaddr('/ip4/10.0.4.2/tcp/9001')) == ('10.0.4.2', 9001)

    @pytest.mark.parametrize(
        'peerid',
        ['12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi']
    )
    def test_p2p_addr_explode(self, peerid):
        assert p2p_addr_explode(
            f'/p2p/{peerid}/x/test'
        ) == (peerid, '/x/test', None)

        assert p2p_addr_explode(
            f'/p2p/{peerid}/x/hello/1.0'
        ) == (peerid, '/x/hello/1.0', '1.0')

        with pytest.raises(ValueError):
            p2p_addr_explode(f'/p2p/{peerid}')

    def test_peerid_reencode(self):
        peerid = peerid_reencode(
            '12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi',
            base='base36'
        )

        assert peerid == 'k51qzi5uqu5dhdmj65s7o239pk7w2knayz61k30js9t66wd6h82yw6iinitcuz'  # noqa
