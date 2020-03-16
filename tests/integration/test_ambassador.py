import sys
from vcr_unittest import VCRTestCase

from tests.utils.base_integration_test_case import BaseIntegrationTestCase
from tests.utils.mockups import mock_ambassador


class TestAmbassador(VCRTestCase, BaseIntegrationTestCase):

    def __init__(self, *args, **kwargs):
        super(TestAmbassador, self).__init__(*args, **kwargs)

    def test_ambassador(self):
        expected_calls = [
            ('call', 'options', {'url': 'http://polyswarmd-fast:8000/v1/wallets/'}),
            ('call', 'request', {'method': 'GET',
                                 'url': 'http://polyswarmd-fast:8000/v1/bounties/parameters/'}),
            ('call', 'request', {'method': 'GET',
                     'url': 'http://polyswarmd-fast:8000/v1/bounties/parameters/'}),
            ('call', 'post', {'url': 'http://polyswarmd-fast:8000/v1/artifacts/'}),
            ('call', 'request',
                     {'method': 'GET',
                      'url': 'http://polyswarmd-fast:8000/v1/wallets/0xECaD0AFcab82F8E4a1CF0E9525265371B586EFbd/'})
        ]

        sys.settrace(self.build_trace_function(['request', 'options', 'post']))

        mock_ambassador.run()

        assert self.calls == expected_calls
