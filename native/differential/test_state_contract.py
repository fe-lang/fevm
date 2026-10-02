from copy import deepcopy
import unittest

from state_contract import compare, validate
from state_corpus import case, encode, frame, transaction, word


class StateContractTests(unittest.TestCase):
    def setUp(self):
        self.case = case('contract', 'test', [transaction([frame('5f')])])
        self.result = [{
            'steps': [{'frame': {'outcome': 'success', 'reason': None, 'gas_remaining': 999998,
                                'stack': [word(0)], 'memory': '0x', 'output': '0x'},
                       'refund_delta': 0, 'refund_counter': 0,
                       'accounts': [{'balance': word(0), 'warm': False} for _ in self.case['watch_accounts']],
                       'storage': [{'value': word(0), 'original': word(0), 'transient': word(0), 'warm': False}
                                   for _ in self.case['watch_slots']]}],
            'refund_counter': 0, 'gas_refunded': 0, 'gas_used': 2,
            'balances': [word(0)] * len(self.case['watch_accounts']),
            'storage': [word(0)] * len(self.case['watch_slots']),
        }]

    def test_rejects_changed_storage_original_transient_warmness_and_refunds(self):
        validate(self.case, self.result)
        for field in ['value', 'original', 'transient', 'warm']:
            actual = deepcopy(self.result)
            actual[0]['steps'][0]['storage'][0][field] = True if field == 'warm' else word(1)
            with self.assertRaises(AssertionError):
                compare(self.case, self.result, actual)
        for field in ['refund_delta', 'refund_counter']:
            actual = deepcopy(self.result)
            actual[0]['steps'][0][field] = -1
            with self.assertRaises(AssertionError):
                compare(self.case, self.result, actual)

    def test_rejects_invalid_cap_and_boolean_gas(self):
        for field, value in [('gas_refunded', 1), ('gas_used', True), ('refund_counter', True)]:
            actual = deepcopy(self.result)
            actual[0][field] = value
            with self.assertRaises(AssertionError):
                validate(self.case, actual)

    def test_rejects_missing_observations_and_operational_outcomes(self):
        actual = deepcopy(self.result)
        actual[0]['steps'][0]['storage'].pop()
        with self.assertRaises(AssertionError):
            validate(self.case, actual)
        actual = deepcopy(self.result)
        actual[0]['steps'][0]['frame']['outcome'] = 'host_allocation_failure'
        with self.assertRaises(AssertionError):
            validate(self.case, actual)

    def test_wire_encoding_bounds(self):
        self.assertTrue(encode(self.case).startswith('0x01'))
        self.case['transactions'][0]['actions'][0]['code'] = '00' * 4096
        with self.assertRaises(ValueError):
            encode(self.case)


if __name__ == '__main__':
    unittest.main()
