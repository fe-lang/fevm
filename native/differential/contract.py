"""Portable frame outcomes, with explicit diagnostic-only fault precedence."""
import re

REASONS = {'stack_underflow', 'stack_overflow', 'invalid_jump', 'invalid_opcode',
           'out_of_gas', 'return_data_oob'}
FIELDS = {'outcome', 'reason', 'gas_remaining', 'stack', 'memory', 'output'}


def validate(frame, gas_limit):
    if not isinstance(frame, dict) or set(frame) != FIELDS:
        raise AssertionError('invalid frame fields')
    if type(frame['gas_remaining']) is not int or not 0 <= frame['gas_remaining'] <= gas_limit:
        raise AssertionError('invalid remaining gas')
    if frame['outcome'] == 'exceptional':
        if (frame['reason'] not in REASONS or frame['gas_remaining'] != 0
                or frame['stack'] is not None or frame['memory'] is not None or frame['output'] != '0x'):
            raise AssertionError('exceptional frame must consume all gas and discard machine results/output')
    elif frame['outcome'] in ('success', 'revert'):
        if frame['reason'] is not None or not isinstance(frame['stack'], list) or len(frame['stack']) > 1024:
            raise AssertionError('invalid completed frame diagnostics')
        if any(not isinstance(word, str) or not re.fullmatch(r'0x[0-9a-f]{64}', word) for word in frame['stack']):
            raise AssertionError('invalid stack word')
        if not isinstance(frame['memory'], str) or not re.fullmatch(r'0x(?:[0-9a-f]{64})*', frame['memory']):
            raise AssertionError('active memory must contain whole words')
        if not isinstance(frame['output'], str) or not re.fullmatch(r'0x(?:[0-9a-f]{2})*', frame['output']):
            raise AssertionError('invalid output bytes')
    else:
        raise AssertionError('operational/unsupported results are not EVM outcomes')


def assert_anchor(frame, anchor):
    for key, expected in anchor.items():
        if frame[key] != expected:
            raise AssertionError(f'specification anchor differs for {key}: {frame[key]!r} != {expected!r}')


def compare(case, reference, observed):
    for frame in [reference, observed]:
        validate(frame, case['gas_limit'])
    # Completed stack and memory are additional machine-state checks. Exceptional
    # partial stacks/memory depend on fault order and are absent from the contract.
    if {k: v for k, v in reference.items() if k != 'reason'} != {k: v for k, v in observed.items() if k != 'reason'}:
        raise AssertionError('portable frame results differ')
    if reference['reason'] != observed['reason']:
        faults = case.get('simultaneous_faults', [])
        if (reference['outcome'] != 'exceptional' or len(set(faults)) < 2
                or reference['reason'] not in faults or observed['reason'] not in faults):
            raise AssertionError('unexpected diagnostic reason difference')
        return {'case': case['name'], 'reference': reference['reason'], 'fevm': observed['reason']}
    return None
