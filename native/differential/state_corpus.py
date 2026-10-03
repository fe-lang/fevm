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
    return dict(sender=address(11), destination=address(12), coinbase=address(13), block_number=word(0),
                access_accounts=[], access_slots=[dict(address=address(12), slot=word(0))] if warm else [],
                commit=commit, actions=actions)


def account(value, balance=0, nonce=0, code=""):
    return dict(address=address(value), balance=word(balance), nonce=nonce, code=code)


def case(name, category, transactions, original=0, anchors=None):
    return dict(name=name, category=category, block_hashes=[], accounts=[account(44, balance=99)],
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
    for current, requested in [
        (0, 0), (1, 0), (255, 0), (256, 0), (257, 0),
        (300, 43), (300, 44), (300, 45), (300, 299), (300, 300), (300, 301),
        (300, (1 << 64) + 44), (300, (1 << 256) - 1),
        ((1 << 64) - 1, (1 << 64) - 257),
        ((1 << 64) - 1, (1 << 64) - 258),
    ]:
        for stored_hash in [0, 0x1234]:
            # Always use PUSH32 so all independent gas anchors are identical.
            code = '7f' + f'{requested:064x}' + '40'
            tx = transaction([frame(code, gas=23)])
            tx['block_number'] = word(current)
            expected = stored_hash if 0 < current - requested <= 256 else 0
            row = case(f'blockhash-{current}-{requested}-{stored_hash}', 'block-history', [tx],
                       anchors={'0.steps.0.frame.stack': [word(expected)],
                                '0.steps.0.frame.gas_remaining': 0})
            row['block_hashes'] = [dict(number=word(requested), hash=word(stored_hash))]
            rows.append(row)
    for code, gas in [('5f40', 21), ('5f40', 22), ('5f40', 23), ('40', 20)]:
        rows.append(case(f'blockhash-gas-{code}-{gas}', 'block-history-gas',
                         [transaction([frame(code, gas=gas)])]))
    rows.extend(account_code_cases())
    assert len({row['name'] for row in rows}) == len(rows)
    return rows


def account_code_cases():
    rows = []
    empty_hash = '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470'
    abc_hash = '0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45'
    profiles = [
        ('absent', None, word(0)), ('empty', account(44), word(0)),
        ('funded', account(44, balance=1), empty_hash),
        ('nonce', account(44, nonce=1), empty_hash),
        ('abc', account(44, code='616263'), abc_hash),
        ('stop', account(44, code='00'), None),
        ('push-data', account(44, code='60ff5b00'), None),
    ]
    for (name, initial, digest), warm, static, high in product(profiles, [False, True], [False, True], [False, True]):
        operand = 44 | ((1 << 255) if high else 0)
        code = push(operand) + '3b' + push(operand) + '3f'
        tx = transaction([frame(code, static=static)])
        if warm:
            tx['access_accounts'] = [address(44)]
        size = len(bytes.fromhex(initial['code'])) if initial else 0
        anchors = {'0.steps.0.frame.stack.0': word(size),
                   '0.steps.0.frame.gas_remaining': 1_000_000 - (100 if warm else 2600) - 100 - 6,
                   '0.steps.0.accounts.6.warm': True}
        if digest is not None:
            anchors['0.steps.0.frame.stack.1'] = digest
        row = case(f'extcode-{name}-{warm}-{static}-{high}', 'account-code-identity', [tx], anchors=anchors)
        row['accounts'] = [initial] if initial else []
        rows.append(row)

    # Storage is deliberately excluded from the EIP-161 empty-account test.
    row = case('extcode-storage-only', 'account-code-identity', [transaction([frame(push(44) + '3f')])],
               anchors={'0.steps.0.frame.stack': [word(0)]})
    row['accounts'] = [account(44)]
    row['storage'] = [dict(address=address(44), slot=word(0), value=word(9))]
    rows.append(row)

    # Sender, destination, coinbase and every Cancun precompile start warm.
    for target in [0, *range(1, 14), 44, 45]:
        row = case(f'extcode-initial-warm-{target}', 'account-code-warmth',
                   [transaction([frame(push(target) + '3f')])],
                   anchors={'0.steps.0.frame.gas_remaining': 1_000_000 - (2 if target == 0 else 3)
                            - (100 if 1 <= target <= 13 else 2600)})
        rows.append(row)

    for op, warm, adjustment in product(['3b', '3f'], [False, True], [-1, 0, 1]):
        spent = 3 + (100 if warm else 2600)
        tx = transaction([frame(push(44) + op, gas=spent + adjustment)])
        if warm:
            tx['access_accounts'] = [address(44)]
        row = case(f'extcode-gas-{op}-{warm}-{adjustment}', 'account-code-gas', [tx],
                   anchors={'0.steps.0.frame.outcome': 'exceptional' if adjustment < 0 else 'success',
                            '0.steps.0.frame.gas_remaining': max(0, adjustment),
                            '0.steps.0.accounts.6.warm': warm or adjustment >= 0})
        row['accounts'] = [account(44, code='616263')]
        rows.append(row)

    external = bytes((i * 17 + 3) % 256 for i in range(137))
    # Include full-width source words and source ranges past the code end.
    for length, source, dest in product([0, 1, 31, 32, 33, 136, 137], [0, 1, 136, 137, 138, 1 << 64, (1 << 256) - 1], [0, 31]):
        code = push(length) + push(source) + push(dest) + push(44) + '3c'
        extent = ((dest + length + 31) // 32 * 32) if length else 0
        memory = bytearray(extent)
        if length:
            copied = external[source:source + length]
            memory[dest:dest + len(copied)] = copied
        row = case(f'extcopy-range-{length}-{source}-{dest}', 'account-code-copy',
                   [transaction([frame(code, static=True)])],
                   anchors={'0.steps.0.frame.memory': '0x' + memory.hex(),
                            '0.steps.0.accounts.6.warm': True})
        row['accounts'] = [account(44, code=external.hex())]
        rows.append(row)

    for high in [1 << 160, 1 << 255]:
        for warm in [False, True]:
            code = push(3) + push(0) + push(0) + push(high | 44) + '3c' + push(44) + '3b'
            tx = transaction([frame(code)])
            if warm:
                tx['access_accounts'] = [address(44)]
            row = case(f'extcopy-address-alias-{high}-{warm}', 'account-code-copy', [tx],
                       anchors={'0.steps.0.frame.memory': '0x616263' + '00' * 29,
                                '0.steps.0.frame.stack': [word(3)],
                                '0.steps.0.frame.gas_remaining': 1_000_000 - (100 if warm else 2600) - 119})
            row['accounts'] = [account(44, code='616263')]
            rows.append(row)

    for source, dest in product([0, (1 << 256) - 1], [0, (1 << 256) - 1]):
        for warm, adjustment in product([False, True], [-1, 0, 1]):
            operands = [0, source, dest, 44]
            spent = sum(2 if value == 0 else 3 for value in operands) + (100 if warm else 2600)
            tx = transaction([frame(''.join(map(push, operands)) + '3c', gas=spent + adjustment)])
            if warm:
                tx['access_accounts'] = [address(44)]
            row = case(f'extcopy-empty-{source}-{dest}-{warm}-{adjustment}', 'account-code-copy-gas', [tx],
                       anchors={'0.steps.0.frame.outcome': 'exceptional' if adjustment < 0 else 'success',
                                '0.steps.0.frame.gas_remaining': max(0, adjustment),
                                '0.steps.0.frame.memory': None if adjustment < 0 else '0x',
                                '0.steps.0.accounts.6.warm': warm or adjustment >= 0})
            rows.append(row)

    for length, dest, warm, adjustment in product([1, 31, 32, 33, 137], [0, 31, 32], [False, True], [-1, 0, 1]):
        operands = [length, 1, dest, 44]
        words = (dest + length + 31) // 32
        spent = sum(2 if value == 0 else 3 for value in operands) + (100 if warm else 2600)
        spent += (length + 31) // 32 * 3 + words * 3 + words * words // 512
        tx = transaction([frame(''.join(map(push, operands)) + '3c', gas=spent + adjustment)])
        if warm:
            tx['access_accounts'] = [address(44)]
        row = case(f'extcopy-gas-{length}-{dest}-{warm}-{adjustment}', 'account-code-copy-gas', [tx],
                   anchors={'0.steps.0.frame.outcome': 'exceptional' if adjustment < 0 else 'success',
                            '0.steps.0.frame.gas_remaining': max(0, adjustment),
                            '0.steps.0.accounts.6.warm': warm or adjustment >= 0})
        row['accounts'] = [account(44, code=external.hex())]
        rows.append(row)

    for name, initial, digest in profiles:
        prefix = push((1 << 256) - 1) + push(0) + '52'
        code = prefix + push(32) + push(0) + push(1) + push(44) + '3c'
        initial_code = bytes.fromhex(initial['code']) if initial else b''
        memory = b'\xff' + initial_code[:32].ljust(32, b'\x00') + bytes(31)
        row = case(f'extcopy-overwrite-{name}', 'account-code-copy', [transaction([frame(code)])],
                   anchors={'0.steps.0.frame.memory': '0x' + memory.hex()})
        row['accounts'] = [initial] if initial else []
        rows.append(row)

    for length, dest in [(1, 1 << 64), (1, 1 << 255), (1, (1 << 256) - 1), ((1 << 256) - 1, 0)]:
        row = case(f'extcopy-overflow-{length}-{dest}', 'account-code-copy-gas',
                   [transaction([frame(push(length) + push(0) + push(dest) + push(44) + '3c')])],
                   anchors={'0.steps.0.frame.outcome': 'exceptional',
                            '0.steps.0.frame.memory': None, '0.steps.0.accounts.6.warm': False})
        rows.append(row)

    for op, operands in [('3b', 1), ('3c', 4), ('3f', 1)]:
        for available in range(operands):
            rows.append(case(f'extcode-underflow-{op}-{available}', 'account-code-stack',
                             [transaction([frame('5f' * available + op)])],
                             anchors={'0.steps.0.frame.reason': 'stack_underflow'}))

    # All four instructions share the same access set; reverted children and
    # failed frames restore it, while successful reads never create accounts.
    reads = [('balance', push(44) + '31'), ('size', push(44) + '3b'),
             ('hash', push(44) + '3f'), ('copy', '5f5f5f' + push(44) + '3c')]
    for (first, first_code), (second, second_code), commit in product(reads, reads, [False, True]):
        tx = transaction([scope([frame(first_code)], commit=commit), frame(second_code)])
        second_spent = (9 if second == 'copy' else 3) + (100 if commit else 2600)
        rows.append(case(f'extcode-shared-{first}-{second}-{commit}', 'account-code-warmth', [tx],
                         anchors={'0.steps.1.accounts.6.warm': commit,
                                  '0.steps.2.frame.gas_remaining': 1_000_000 - second_spent}))
    for ending in ['5f5ffd', 'fe']:
        rows.append(case(f'extcode-failed-{ending}', 'account-code-warmth',
                         [transaction([frame(push(44) + '3f' + ending), frame(push(44) + '3b')])],
                         anchors={'0.steps.0.accounts.6.warm': False,
                                  '0.steps.1.frame.gas_remaining': 997397}))
    for commit in [False, True]:
        row = case(f'extcode-transaction-{commit}', 'account-code-warmth',
                   [transaction([frame(push(44) + '3f')], commit=commit), transaction([frame(push(44) + '3f')])],
                   anchors={'1.steps.0.frame.gas_remaining': 997397, '1.steps.0.frame.stack': [abc_hash]})
        row['accounts'] = [account(44, code='616263')]
        rows.append(row)
    return rows


def payload(case):
    return {key: value for key, value in case.items() if key not in ['name', 'category', 'anchors']}


def encode(case):
    """Version 3: explicit accounts with balance, nonce and arbitrary code bytes."""
    data = bytearray([3])

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

    sequence(case['block_hashes'], [('number', 32), ('hash', 32)])
    integer(len(case['accounts']), 2)
    for account in case['accounts']:
        integer(account['address'], 20)
        integer(account['balance'], 32)
        integer(account['nonce'], 8)
        code = bytes.fromhex(account['code'].removeprefix('0x'))
        integer(len(code), 2)
        data.extend(code)
    sequence(case['storage'], [('address', 20), ('slot', 32), ('value', 32)])
    sequence(case['watch_accounts'], [(None, 20)])
    sequence(case['watch_slots'], [('address', 20), ('slot', 32)])
    integer(len(case['transactions']), 2)
    for transaction in case['transactions']:
        for key in ['sender', 'destination', 'coinbase']:
            integer(transaction[key], 20)
        integer(transaction['block_number'], 32)
        integer(transaction['commit'], 1)
        sequence(transaction['access_accounts'], [(None, 20)])
        sequence(transaction['access_slots'], [('address', 20), ('slot', 32)])
        actions(transaction['actions'])
    if len(data) > 4096:
        raise ValueError('state case exceeds the native harness input capacity')
    return '0x' + data.hex()
