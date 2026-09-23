"""Deterministic, terminating Cancun frames for the first interpreter slice."""
import random

MASK = (1 << 256) - 1


def push(value):
    data = value.to_bytes(max(1, (value.bit_length() + 7) // 8), 'big')
    return bytes([0x5f + len(data)]) + data


def success(*stack, output='0x', outcome='success', gas_remaining=None, memory=None):
    frame = {'outcome': outcome, 'reason': None, 'stack': [f'0x{x:064x}' for x in stack], 'output': output}
    if gas_remaining is not None:
        frame['gas_remaining'] = gas_remaining
    if memory is not None:
        frame['memory'] = memory
    return frame


def exceptional(reason):
    return {'outcome': 'exceptional', 'reason': reason, 'gas_remaining': 0,
            'stack': None, 'memory': None, 'output': '0x'}


def cases():
    result = []

    def add(name, category, code, calldata=b'', expected=None, gas_limit=1_000_000, simultaneous_faults=None):
        assert len(code) <= 4096 and len(calldata) <= 4096
        row = {'name': name, 'category': category, 'code': code.hex(), 'calldata': calldata.hex(), 'gas_limit': gas_limit}
        if simultaneous_faults:
            row['simultaneous_faults'] = simultaneous_faults
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
        ('jump-into-data', '600456605b00', exceptional('invalid_jump')),
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
        add(f'dup-{depth}', 'stack', stack + bytes([0x7f + depth]),
            expected=success(*range(depth + 1), 1))
        add(f'swap-{depth}', 'stack', stack + bytes([0x8f + depth]),
            expected=success(depth, *range(1, depth), 0))
        add(f'dup-underflow-{depth}', 'stack', b'\x5f' * (depth - 1) + bytes([0x7f + depth]),
            expected=exceptional('stack_underflow'))
        add(f'swap-underflow-{depth}', 'stack', b'\x5f' * depth + bytes([0x8f + depth]),
            expected=exceptional('stack_underflow'))
    for op in [*binary, 0x08, 0x09, 0x15, 0x19, 0x50, 0x56, 0x57]:
        arity = 3 if op in (8, 9) else 1 if op in (0x15, 0x19, 0x50, 0x56) else 2
        for available in range(arity):
            add(f'underflow-{op:02x}-{available}', 'stack', b'\x5f' * available + bytes([op]),
                expected=exceptional('stack_underflow'))
    add('stack-limit', 'stack', b'\x5f' * 1024, expected=success(*([0] * 1024)))
    add('stack-overflow', 'stack', b'\x5f' * 1025,
        expected=exceptional('stack_overflow'))
    add('dup-overflow', 'stack', b'\x5f' * 1024 + b'\x80',
        expected=exceptional('stack_overflow'))
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
    # Memory anchors include exact gas and all active bytes, independently of
    # either engine's machine-state representation.
    for offset in [0, 31, 32, 63, 64, 703, 704, 735, 736, 8191, 8192, 9000, 16384]:
        size = (offset + 32) // 32 * 32
        words = size // 32
        cost = 3 * words + words * words // 512
        memory = bytearray(size)
        memory[offset] = 0xab
        remaining = 1_000_000 - cost - 13
        add(f'mstore8-extent-{offset}', 'memory', push(0xab) + push(offset) + b'\x53\x59\x5a',
            expected=success(size, remaining, gas_remaining=remaining, memory='0x' + memory.hex()))

    for opcode, label in [(0x37, 'calldata'), (0x39, 'code')]:
        data = bytes(range(64))
        for source in [0, 31, 63, 64, 4097, 1 << 64, MASK - 1, MASK]:
            for length in [0, 1, 33]:
                destination = MASK if length == 0 else 31
                code = push(length) + push(source) + push(destination) + bytes([opcode]) + b'\x59'
                size = (destination + length + 31) // 32 * 32 if length else 0
                memory = bytearray(size)
                source_bytes = data if opcode == 0x37 else code
                copied = source_bytes[source:source + length]
                if length:
                    memory[destination:destination + length] = copied.ljust(length, b'\0')
                words = size // 32
                cost = 14 + 3 * ((length + 31) // 32) + 3 * words + words * words // 512
                add(f'{label}-copy-{source:x}-{length}', 'memory', code, data,
                    expected=success(size, gas_remaining=1_000_000 - cost, memory='0x' + memory.hex()))
        # Zero-fill must overwrite old bytes, including a partially readable prefix.
        for source in [63, MASK]:
            code = push(MASK) + push(0) + b'\x52' + push(32) + push(source) + push(0) + bytes([opcode]) + push(0) + b'\x51'
            add(f'{label}-overwrite-{source:x}', 'memory', code, data)

    for source in [0, 1, 31, 32, 63, 64, MASK - 31, MASK]:
        data = bytes(range(64))
        expected = int.from_bytes(data[source:source + 32].ljust(32, b'\0'), 'big')
        add(f'calldataload-{source:x}', 'memory', push(source) + b'\x35', data,
            expected=success(expected, gas_remaining=999994, memory='0x'))

    for dest, source, length in [(0, 0, 64), (1, 0, 63), (0, 1, 63), (31, 0, 33),
                                 (0, 31, 33), (64, 0, 32), (0, 64, 32), (31, 63, 34),
                                 (128, 256, 1), (9000, 0, 33)]:
        data = bytes(range(64))
        size = (max(64, dest + length, source + length) + 31) // 32 * 32
        memory = bytearray(data.ljust(size, b'\0'))
        memory[dest:dest + length] = memory[source:source + length]
        code = push(64) + push(0) + push(0) + b'\x37'
        code += push(length) + push(source) + push(dest) + b'\x5e' + push(size) + push(0) + b'\xf3'
        words = size // 32
        cost = 36 + 3 * ((length + 31) // 32) + 3 * words + words * words // 512
        add(f'mcopy-{dest}-{source}-{length}', 'memory', code, data,
            expected=success(output='0x' + memory.hex(), gas_remaining=1_000_000 - cost, memory='0x' + memory.hex()))

    for opcode in [0x37, 0x39, 0x5e]:
        add(f'empty-copy-{opcode:02x}', 'memory', push(0) + push(MASK) + push(MASK) + bytes([opcode]) + b'\x59',
            expected=success(0, gas_remaining=999986, memory='0x'))
        for offset, length in [(MASK, 1), (1, MASK), (1 << 42, 1), ((1 << 42) - 1, 1)]:
            add(f'unpayable-copy-{opcode:02x}-{offset:x}-{length:x}', 'gas',
                push(length) + push(0) + push(offset) + bytes([opcode]), expected=exceptional('out_of_gas'))

    for opcode in [0x51, 0x52, 0x53, 0xf3, 0xfd]:
        code = (b'' if opcode == 0x51 else push(1)) + push(MASK) + bytes([opcode])
        add(f'unpayable-memory-{opcode:02x}', 'gas', code, expected=exceptional('out_of_gas'))
    for opcode in [0xf3, 0xfd]:
        add(f'empty-output-{opcode:02x}', 'memory', push(0) + push(MASK) + bytes([opcode]),
            expected=success(outcome='success' if opcode == 0xf3 else 'revert', gas_remaining=999994, memory='0x'))
        add(f'large-output-{opcode:02x}', 'memory', push(9000) + push(0) + bytes([opcode]),
            expected=success(outcome='success' if opcode == 0xf3 else 'revert', output='0x' + '00' * 9000,
                             gas_remaining=998993, memory='0x' + '00' * 9024))

    for source, length in [(0, 0), (1, 0), (MASK, 0), (0, 1), (MASK, 1)]:
        code = push(length) + push(source) + push(0) + b'\x3e'
        expected = success(gas_remaining=999988, memory='0x') if source == length == 0 else exceptional('return_data_oob')
        add(f'returndata-bounds-{source:x}-{length}', 'memory', code, expected=expected)
    add('returndata-empty-max-destination', 'memory', push(0) + push(0) + push(MASK) + b'\x3e',
        expected=success(gas_remaining=999988, memory='0x'))
    for destination, source, length, gas in [(1 << 255, 1, 1, 1_000_000), (0, 0, 1, 15), (0, 1, 0, 11)]:
        add(f'returndata-simultaneous-{destination:x}-{length}-{gas}', 'gas',
            push(length) + push(source) + push(destination) + b'\x3e', gas_limit=gas,
            expected={'outcome': 'exceptional', 'gas_remaining': 0, 'output': '0x'},
            simultaneous_faults=['out_of_gas', 'return_data_oob'])

    for gas in [0, 1, 2, 3]:
        add(f'push0-budget-{gas}', 'gas', b'\x5f', gas_limit=gas,
            expected=success(0, gas_remaining=gas - 2, memory='0x') if gas >= 2 else exceptional('out_of_gas'))
    for gas in [11, 12, 13]:
        add(f'mstore8-budget-{gas}', 'gas', push(0xab) + push(31) + b'\x53', gas_limit=gas,
            expected=success(gas_remaining=gas - 12, memory='0x' + '00' * 31 + 'ab') if gas >= 12 else exceptional('out_of_gas'))
    add('zero-gas-stop', 'gas', b'\x00', gas_limit=0, expected=success(gas_remaining=0, memory='0x'))
    add('gas-includes-own-cost', 'gas', b'\x5a\x5a', gas_limit=10,
        expected=success(8, 6, gas_remaining=6, memory='0x'))
    add('gas-u64-max', 'gas', b'\x5a', gas_limit=(1 << 64) - 1,
        expected=success((1 << 64) - 3, gas_remaining=(1 << 64) - 3, memory='0x'))
    add('loop-exhaustion', 'gas', bytes.fromhex('5b5f56'), gas_limit=100, expected=exceptional('out_of_gas'))
    assert len({case['name'] for case in result}) == len(result)
    return result
