"""Deterministic, terminating Cancun frames for the first interpreter slice."""
import random

MASK = (1 << 256) - 1


def push(value):
    data = value.to_bytes(max(1, (value.bit_length() + 7) // 8), 'big')
    return bytes([0x5f + len(data)]) + data


def success(*stack, output='0x', status='success'):
    return {'status': status, 'stack': [f'0x{x:064x}' for x in stack], 'output': output}


def cases():
    result = []

    def add(name, category, code, calldata=b'', expected=None):
        assert len(code) <= 4096 and len(calldata) <= 4096
        row = {'name': name, 'category': category, 'code': code.hex(), 'calldata': calldata.hex()}
        if expected is not None:
            row['expected'] = expected
        result.append(row)

    # Small independently specified anchors catch a misconfigured adapter/oracle.
    for name, code, expected in [
        ('empty', '', success()),
        ('sub-order', '600260030300', success(1)),
        ('div-order', '6002600704', success(3)),
        ('exp-order', '600360020a', success(8)),
        ('addmod-order', '60076004600508', success(2)),
        ('mulmod-order', '60076004600509', success(6)),
        ('sdiv-min-overflow', (push(MASK) + push(1 << 255) + b'\x05').hex(), success(1 << 255)),
        ('push-padding', '61ab', success(0xab00)),
        ('jump-into-data', '600456605b00', {'status': 'invalid_jump', 'stack': None, 'output': '0x'}),
    ]:
        add(name, 'anchors', bytes.fromhex(code), expected=expected)

    rng = random.Random(0xFECA)
    edges = [0, 1, 2, 7, 127, 128, 255, 256, 257, MASK, MASK - 1]
    for bit in [63, 64, 127, 128, 191, 192, 255]:
        edges.extend([(1 << bit) - 1, 1 << bit, (1 << bit) + 1])
    edges = list(dict.fromkeys(edges))
    pairs = [(a, b) for a in edges for b in [0, 1, 2, 7, MASK, 1 << 255]]
    pairs += [(b, a) for a, b in pairs]
    pairs += [(rng.getrandbits(256), rng.getrandbits(256)) for _ in range(64)]
    binary = [*range(1, 8), 0x0a, 0x0b, *range(0x10, 0x15), *range(0x16, 0x19), *range(0x1a, 0x1e)]
    for op in [*binary, 0x08, 0x09, 0x15, 0x19]:
        operations = []
        for a, b in pairs:
            if op in (0x08, 0x09):
                for modulus in [0, 1, 7, (1 << 128) + 1, MASK]:
                    operations.append(push(modulus) + push(b) + push(a) + bytes([op]))
            elif op in (0x15, 0x19):
                operations.append(push(a) + bytes([op]))
            else:
                operations.append(push(b) + push(a) + bytes([op]))
        # Keep every result on the stack, but pack independent operations into
        # bounded frames to avoid paying native process startup for each word.
        code = push(0xdecaf)
        count = 0
        chunk = 0
        for operation in operations:
            if len(code) + len(operation) > 4000 or count == 128:
                add(f'op-{op:02x}-{chunk}', 'arithmetic', code)
                code, count, chunk = push(0xdecaf), 0, chunk + 1
            code += operation
            count += 1
        add(f'op-{op:02x}-{chunk}', 'arithmetic', code)

    add('push0', 'push', b'\x5f', expected=success(0))
    for width in range(1, 33):
        for present in range(width + 1):
            data = bytes((i * 37 + 0xab) & 255 for i in range(present))
            value = int.from_bytes(data.ljust(width, b'\0'), 'big')
            add(f'push-{width}-present-{present}', 'push', bytes([0x5f + width]) + data,
                expected=success(value))
        # CODESIZE sees the original length even when the last PUSH is padded.
        add(f'codesize-push-{width}', 'push', bytes([0x38, 0x5f + width]), expected=success(2, 0))

    for width in range(1, 33):
        for offset in range(width):
            code = push(4 + offset) + b'\x56' + bytes([0x5f + width]) + b'\x5b' * width + b'\x00'
            add(f'jump-push-{width}-byte-{offset}', 'jump', code)
        for condition in [0, 1]:
            for offset in {0, width - 1}:
                code = push(condition) + push(7 + offset) + b'\x57\x00'
                code += bytes([0x5f + width]) + b'\x5b' * width + b'\x00'
                add(f'jumpi-{condition}-push-{width}-byte-{offset}', 'jump', code)
        # A real destination immediately after PUSH data must remain valid.
        destination = 4 + width
        code = push(destination) + b'\x56' + bytes([0x5f + width]) + b'\x5b' * width
        add(f'jump-after-push-{width}', 'jump', code + b'\x5b\x60\x2a', expected=success(42))
    for dest in [0, 1, 2, 3, 4, 4096, 1 << 64, MASK]:
        add(f'jump-destination-{dest:x}', 'jump', push(dest) + b'\x56')
        add(f'untaken-jumpi-{dest:x}', 'jump', b'\x5f' + push(dest) + b'\x57', expected=success())
    add('jump-over-invalid', 'jump', bytes.fromhex('6005560c005b6009'), expected=success(9))
    add('last-code-byte-push32', 'jump', bytes.fromhex('610ffe56') + b'\0' * 4090 + b'\x5b\x7f',
        expected=success(0))

    for depth in range(1, 17):
        stack = b''.join(push(x) for x in range(depth + 1))
        add(f'dup-{depth}', 'stack', stack + bytes([0x7f + depth]))
        add(f'swap-{depth}', 'stack', stack + bytes([0x8f + depth]))
        add(f'dup-underflow-{depth}', 'stack', b'\x5f' * (depth - 1) + bytes([0x7f + depth]))
        add(f'swap-underflow-{depth}', 'stack', b'\x5f' * depth + bytes([0x8f + depth]))
    for op in [*binary, 0x08, 0x09, 0x15, 0x19, 0x50, 0x56, 0x57]:
        arity = 3 if op in (8, 9) else 1 if op in (0x15, 0x19, 0x50, 0x56) else 2
        for available in range(arity):
            add(f'underflow-{op:02x}-{available}', 'stack', b'\x5f' * available + bytes([op]))
    add('stack-limit', 'stack', b'\x5f' * 1024)
    add('stack-overflow', 'stack', b'\x5f' * 1025)
    add('dup-overflow', 'stack', b'\x5f' * 1024 + b'\x80')
    for name, code, calldata in [
        ('stop', '00fe', ''),
        ('invalid', 'fe', ''),
        ('pc', '585858', ''),
        ('return-word', '602a5f5260205ff3', ''),
        ('revert-word', '602a5f5260205ffd', ''),
        ('return-empty', '5f5ff3', ''),
        ('calldata-return', '60025f5f3760025ff3', '1234'),
        ('codecopy-original', '600460005f3960045ff3', ''),
    ]:
        add(name, 'frame', bytes.fromhex(code), bytes.fromhex(calldata))
    assert len({case['name'] for case in result}) == len(result)
    return result
