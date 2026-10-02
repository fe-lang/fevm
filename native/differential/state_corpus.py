"""Deterministic Cancun state-access sequences and their native wire encoding."""
from itertools import product
import random


def address(value):
    return f'0x{value:040x}'


def word(value):
    return f'0x{value:064x}'


def push(value):
    if value == 0:
        return '5f'
    size = (value.bit_length() + 7) // 8
    return f'{0x5f + size:02x}{value:0{size * 2}x}'


def store(value, slot=0, transient=False):
    return push(value) + push(slot) + ('5d' if transient else '55')


def frame(code, gas=1_000_000, static=False):
    return dict(kind='frame', code=code, calldata='', gas_limit=gas, is_static=static)


def scope(actions, commit, static=False):
    return dict(kind='scope', actions=actions, commit=commit, is_static=static)


def transaction(actions, *, warm=False, commit=True):
    return dict(sender=address(11), destination=address(12), coinbase=address(13),
                access_accounts=[], access_slots=[dict(address=address(12), slot=word(0))] if warm else [],
                commit=commit, actions=actions)


def case(name, category, transactions, original=0, anchors=None):
    return dict(name=name, category=category, balances=[dict(address=address(44), value=word(99))],
                storage=[dict(address=address(12), slot=word(0), value=word(original))],
                watch_accounts=[address(x) for x in [0, 1, 10, 11, 12, 13, 44, 45]],
                watch_slots=[dict(address=address(12), slot=word(x)) for x in [0, 1, 2]],
                transactions=transactions, anchors=anchors or {})


def cases():
    rows = []
    # EIP-2200 sequence anchors adjusted for EIP-2929/3529 Cancun constants.
    # Use PUSH1 even for zero here to retain the specification vectors' bytecode.
    vectors = [
        (0, [0, 0], 2312, 0), (0, [0, 1], 22212, 0), (0, [1, 0], 22212, 19900),
        (0, [1, 2], 22212, 0), (0, [1, 1], 22212, 0), (1, [0, 0], 5112, 4800),
        (1, [0, 1], 5112, 2800), (1, [0, 2], 5112, 0), (1, [2, 0], 5112, 4800),
        (1, [2, 3], 5112, 0), (1, [2, 1], 5112, 2800), (1, [2, 2], 5112, 0),
        (1, [1, 0], 5112, 4800), (1, [1, 2], 5112, 0), (1, [1, 1], 2312, 0),
        (0, [1, 0, 1], 42218, 19900), (1, [0, 1, 0], 8018, 7600),
    ]
    for index, (original, values, cold_spent, refund) in enumerate(vectors):
        for warm in [False, True]:
            spent = cold_spent - (2100 if warm else 0)
            code = ''.join(f'60{value:02x}600055' for value in values)
            rows.append(case(f'net-storage-{index}-{warm}', 'net-storage-anchors',
                             [transaction([frame(code)], warm=warm)], original,
                             {'0.steps.0.frame.gas_remaining': 1_000_000 - spent,
                              '0.steps.0.refund_delta': refund,
                              '0.gas_refunded': min(refund, spent // 5), '0.storage.0': word(values[-1])}))
    for original, first, second, third, warm in product([0, 1, 2], [0, 1, 2], [0, 1, 2], [0, 1, 2], [False, True]):
        actions = [frame(store(value)) for value in [first, second, third]]
        rows.append(case(f'separate-frames-{original}-{first}-{second}-{third}-{warm}',
                         'storage-frame-sequences', [transaction(actions, warm=warm)], original))
    for target in [0, *range(1, 14), 44, 45]:
        for high in [False, True]:
            operand = target | ((1 << 255) if high else 0)
            code = push(operand) + '31' + push(target) + '31'
            spent = 6 + (100 if 1 <= target <= 13 else 2600) + 100
            if target == 0:
                spent -= 1 + (not high)
            rows.append(case(f'balance-{target}-{high}', 'account-warming', [transaction([frame(code)])],
                             anchors={'0.steps.0.frame.gas_remaining': 1_000_000 - spent,
                                      '0.steps.0.frame.stack': [word(99 if target == 44 else 0)] * 2}))
    for warm in [False, True]:
        for code, boundary in [('5f54', 102 if warm else 2102), ('5f5f55', 2305),
                               ('60015f55', 20005 if warm else 22105), ('60015f5d', 105), ('5f5c', 102)]:
            for gas in [0, boundary - 1, boundary, boundary + 1]:
                rows.append(case(f'gas-boundary-{code}-{warm}-{gas}', 'gas-boundaries',
                                 [transaction([frame(code, gas=gas)], warm=warm)]))
    for opcode in ['55', '5d']:
        for value in [0, 1]:
            rows.append(case(f'static-write-{opcode}-{value}', 'static',
                             [transaction([frame(push(value) + '5f' + opcode, static=True)])],
                             anchors={'0.steps.0.frame.outcome': 'exceptional',
                                      '0.steps.0.frame.reason': 'static_write', '0.storage.0': word(0)}))
    rows.extend([
        case('inherited-static', 'static', [transaction([scope([frame(store(1)), frame('5f545f5c')], True, True)])]),
        case('child-commit-parent-revert', 'checkpoints', [transaction([
            scope([frame(store(0) + store(9, transient=True) + push(44) + '31'),
                   scope([frame(store(1))], True)], False), frame('5f545f5c' + push(44) + '31')])], 1),
        case('child-revert-parent-commit', 'checkpoints', [transaction([
            scope([frame(store(0)), scope([frame(store(1))], False), frame('5f54')], True)])], 1),
        case('revert-after-writes', 'frame-revert', [transaction([frame(store(1) + store(9, transient=True) + '5f5ffd'), frame('5f545f5c')])]),
        case('invalid-after-clear', 'frame-revert', [transaction([frame(store(0) + 'fe'), frame('5f54')])], 1),
        case('out-of-gas-after-clear', 'frame-revert', [transaction([frame('5f5f555f', gas=5005), frame('5f54')])], 1),
        case('zero-original-after-nested-revert', 'checkpoints', [transaction([
            scope([frame(store(2))], False), frame(store(1)), frame(store(0))])]),
        case('access-list-retained-on-revert', 'access-lists', [transaction([
            scope([frame('5f54' + push(44) + '31')], False), frame('5f54')], warm=True)]),
        case('repeat-transaction', 'transaction-boundaries', [transaction([frame(store(7) + store(9, transient=True))]),
            transaction([frame('5f5c' + store(0))])]),
        case('abort-transaction', 'transaction-boundaries', [transaction([frame(store(0))], commit=False),
            transaction([frame(store(0))])], 7),
        case('refund-below-cap', 'refund-cap', [transaction([frame(store(0) + ''.join(push(x) + '3150' for x in range(100, 110)))])], 1,
             {'0.refund_counter': 4800, '0.gas_refunded': 4800}),
        case('full-width-storage', 'word-boundaries', [transaction([frame(store((1 << 256) - 1, 2)), frame(push(2) + '54'),
            frame(store(0, 2))])]),
    ])
    access = transaction([frame(push(44) + '31' + '5f54')])
    access['access_accounts'] = [address(44), address(44)]
    access['access_slots'] = [dict(address=address(12), slot=word(0))] * 2
    rows.append(case('duplicate-access-list-entries', 'access-lists', [access],
                     anchors={'0.steps.0.frame.gas_remaining': 999795}))
    rng = random.Random(0xFE2929)
    for index in range(64):
        actions = []
        for _ in range(rng.randrange(2, 7)):
            code = ''
            for _ in range(rng.randrange(1, 6)):
                slot, value = rng.randrange(3), rng.choice([0, 1, 2, 17, (1 << 256) - 1])
                op = rng.randrange(5)
                code += (store(value, slot) if op == 0 else store(value, slot, True) if op == 1
                         else push(slot) + ('54' if op == 2 else '5c') if op < 4
                         else push(rng.choice([0, 1, 10, 11, 12, 13, 44, 45])) + '31')
            code += rng.choice(['', '', '5f5ffd', 'fe'])
            actions.append(frame(code, gas=rng.choice([2300, 5000, 25000, 100000]), static=rng.randrange(5) == 0))
        if index % 2:
            actions = [scope(actions[:2], commit=index % 3 != 0), *actions[2:]]
        rows.append(case(f'mixed-state-{index}', 'seeded-state-sequences',
                         [transaction(actions, warm=index % 3 == 0)], original=index % 3))
    assert len({row['name'] for row in rows}) == len(rows)
    return rows


def payload(case):
    return {key: value for key, value in case.items() if key not in ['name', 'category', 'anchors']}


def encode(case):
    """Version 1: big-endian lengths/words; recursive actions match the JSON schema."""
    data = bytearray([1])

    def integer(value, size):
        data.extend((int(value, 16) if isinstance(value, str) else value).to_bytes(size, 'big'))

    def sequence(rows, fields):
        integer(len(rows), 2)
        for row in rows:
            for field, size in fields:
                integer(row[field] if field else row, size)

    def actions(rows):
        integer(len(rows), 2)
        for row in rows:
            integer(row['kind'] == 'scope', 1)
            integer(row['is_static'], 1)
            if row['kind'] == 'scope':
                integer(row['commit'], 1)
                actions(row['actions'])
            else:
                integer(row['gas_limit'], 8)
                for name in ['code', 'calldata']:
                    blob = bytes.fromhex(row[name].removeprefix('0x'))
                    integer(len(blob), 2)
                    data.extend(blob)

    sequence(case['balances'], [('address', 20), ('value', 32)])
    sequence(case['storage'], [('address', 20), ('slot', 32), ('value', 32)])
    sequence(case['watch_accounts'], [(None, 20)])
    sequence(case['watch_slots'], [('address', 20), ('slot', 32)])
    integer(len(case['transactions']), 2)
    for transaction in case['transactions']:
        for key in ['sender', 'destination', 'coinbase']:
            integer(transaction[key], 20)
        integer(transaction['commit'], 1)
        sequence(transaction['access_accounts'], [(None, 20)])
        sequence(transaction['access_slots'], [('address', 20), ('slot', 32)])
        actions(transaction['actions'])
    if len(data) > 4096:
        raise ValueError('state case exceeds the native harness input capacity')
    return '0x' + data.hex()
