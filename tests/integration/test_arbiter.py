import sys
from vcr_unittest import VCRTestCase
from tests.utils.base_integration_test_case import BaseIntegrationTestCase
from tests.utils.mockups import mock_arbiter


class TestArbiter(VCRTestCase, BaseIntegrationTestCase):

    def __init__(self, *args, **kwargs):
        super(TestArbiter, self).__init__(*args, **kwargs)

    def test_arbiter(self):
        expected_calls = [
            ('call', 'options', {'url': 'http://polyswarmd-fast:8000/v1/wallets/'}),
            ('call', 'request', {'method': 'GET', 'url': 'http://polyswarmd-fast:8000/v1/bounties/parameters/'})]

        sys.settrace(self.build_trace_function(['request', 'options', 'post']))

        mock_arbiter.run()

        assert self.calls == expected_calls
