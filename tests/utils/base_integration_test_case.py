from deepdiff import DeepDiff
from pkg_resources import resource_filename
from unittest import TestCase

from tests.utils.fixtures import WebsocketMockManager

TestCase.maxDiff = None


class BaseIntegrationTestCase(TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseIntegrationTestCase, self).__init__(*args, **kwargs)
        self.websocket_mock_manager = WebsocketMockManager()
        self.calls = []

    def build_trace_function(self, functions):

        def trace_function(frame, event, arg, indent=[0]):
            method_name = frame.f_code.co_name

            if (event == 'call' or event == 'return') and method_name in functions:
                method_arguments = {}
                for i in range(frame.f_code.co_argcount):
                    name = frame.f_code.co_varnames[i]
                    value = frame.f_locals[name]
                    if name is not 'self':
                        method_arguments[name] = value

                self.calls += [(event, method_name, method_arguments)]

        return trace_function

    def setUp(self):
        super(BaseIntegrationTestCase, self).setUp()
        self.websocket_mock_manager.start()

    def tearDown(self):
        super(BaseIntegrationTestCase, self).tearDown()
        self.websocket_mock_manager.stop()

    @staticmethod
    def _assert_json_dicts_equal(first, second, exclude_paths=None):
        diff = DeepDiff(first, second, ignore_order=True, exclude_paths=exclude_paths)
        if diff:
            raise AssertionError(f'Input JSON differ: {diff}')

    @staticmethod
    def _get_test_resource_full_path(resource):
        return resource_filename('tests.resources', resource)
