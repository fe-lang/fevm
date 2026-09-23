import unittest

from contract import compare, validate


def halt(reason):
    return dict(outcome='exceptional', reason=reason, gas_remaining=0, stack=None, memory=None, output='0x')


class FrameContractTests(unittest.TestCase):
    def test_simultaneous_faults_retain_both_reasons(self):
        case = dict(name='bounds-and-gas', gas_limit=100,
                    simultaneous_faults=['return_data_oob', 'out_of_gas'])
        self.assertEqual(compare(case, halt('return_data_oob'), halt('out_of_gas')),
                         dict(case='bounds-and-gas', reference='return_data_oob', fevm='out_of_gas'))

    def test_single_fault_reason_is_still_checked(self):
        with self.assertRaises(AssertionError):
            compare(dict(name='one-fault', gas_limit=100), halt('stack_underflow'), halt('stack_overflow'))

    def test_exceptional_gas_output_and_operational_failures_are_not_normalized(self):
        for patch in [dict(gas_remaining=1), dict(output='0xab'), dict(stack=[]), dict(memory='0x'),
                      dict(outcome='host_allocation'), dict(reason='unsupported_result')]:
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                validate(halt('out_of_gas') | patch, 100)

    def test_completed_result_differences_still_fail(self):
        case = dict(name='completed', gas_limit=100)
        frame = dict(outcome='success', reason=None, gas_remaining=97, stack=[], memory='0x', output='0x')
        for patch in [dict(outcome='revert'), dict(gas_remaining=96), dict(output='0xab'),
                      dict(memory='0x' + '00' * 32), dict(stack=['0x' + '00' * 32])]:
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                compare(case, frame, frame | patch)
        self.assertIsNone(compare(case, frame, frame))


if __name__ == '__main__':
    unittest.main()
