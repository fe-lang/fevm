"""Strict stateful result schema and transaction accounting invariants."""
import re

from contract import validate as validate_frame

WORD = re.compile(r'0x[0-9a-f]{64}')
STEP_FIELDS = {'frame', 'refund_delta', 'refund_counter', 'accounts', 'storage'}
TX_FIELDS = {'steps', 'refund_counter', 'gas_refunded', 'gas_used', 'balances', 'storage'}


def flattened(actions):
    for action in actions:
        if action['kind'] == 'scope':
            yield from flattened(action['actions'])
        yield action


def signed(value):
    if type(value) is not int or not -(1 << 127) <= value < 1 << 127:
        raise AssertionError('invalid signed refund')


def words(values, count):
    if not isinstance(values, list) or len(values) != count or any(
            not isinstance(value, str) or not WORD.fullmatch(value) for value in values):
        raise AssertionError('invalid state words')


def validate(case, results):
    if not isinstance(results, list) or len(results) != len(case['transactions']):
        raise AssertionError('wrong transaction result count')
    for transaction, result in zip(case['transactions'], results, strict=True):
        if not isinstance(result, dict) or set(result) != TX_FIELDS:
            raise AssertionError('invalid transaction fields')
        actions = list(flattened(transaction['actions']))
        if not isinstance(result['steps'], list) or len(result['steps']) != len(actions):
            raise AssertionError('wrong step count')
        spent = 0
        for action, step in zip(actions, result['steps'], strict=True):
            if not isinstance(step, dict) or set(step) != STEP_FIELDS:
                raise AssertionError('invalid step fields')
            signed(step['refund_delta'])
            signed(step['refund_counter'])
            if action['kind'] == 'frame':
                validate_frame(step['frame'], action['gas_limit'])
                spent += action['gas_limit'] - step['frame']['gas_remaining']
                if step['frame']['outcome'] != 'success' and step['refund_delta'] != 0:
                    raise AssertionError('failed frame retained refund delta')
            elif step['frame'] is not None or step['refund_delta'] != 0:
                raise AssertionError('scope result contains frame data')
            if not isinstance(step['accounts'], list) or len(step['accounts']) != len(case['watch_accounts']):
                raise AssertionError('invalid watched accounts')
            for account in step['accounts']:
                if not isinstance(account, dict) or set(account) != {'balance', 'warm'} or type(account['warm']) is not bool:
                    raise AssertionError('invalid account observation')
                words([account['balance']], 1)
            if not isinstance(step['storage'], list) or len(step['storage']) != len(case['watch_slots']):
                raise AssertionError('invalid watched storage')
            for slot in step['storage']:
                if not isinstance(slot, dict) or set(slot) != {'value', 'original', 'transient', 'warm'} or type(slot['warm']) is not bool:
                    raise AssertionError('invalid storage observation')
                words([slot['value'], slot['original'], slot['transient']], 3)
        signed(result['refund_counter'])
        if not transaction['commit'] and result['refund_counter'] != 0:
            raise AssertionError('aborted transaction retained refund counter')
        if any(type(result[key]) is not int for key in ['gas_refunded', 'gas_used']):
            raise AssertionError('invalid transaction gas')
        refund = min(max(result['refund_counter'], 0), spent // 5)
        if result['gas_refunded'] != refund or result['gas_used'] != spent - refund:
            raise AssertionError('transaction gas/refund accounting differs')
        words(result['balances'], len(case['watch_accounts']))
        words(result['storage'], len(case['watch_slots']))


def assert_anchors(case, results):
    for path, expected in case['anchors'].items():
        actual = results
        for part in path.split('.'):
            actual = actual[int(part)] if isinstance(actual, list) else actual[part]
        if actual != expected:
            raise AssertionError(f'{case["name"]} anchor {path}: {actual!r} != {expected!r}')


def compare(case, reference, observed):
    validate(case, reference)
    validate(case, observed)
    if reference != observed:
        raise AssertionError('state, warming, gas, refunds or frame results differ')
