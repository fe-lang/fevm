#!/usr/bin/env python3
"""Write state tests that loop KECCAK256 and the precompiles on inputs that do
their full work, for `run.py --fevm-only`. A call that fails or returns nothing
hits INVALID, so the transaction halts and the bad input shows in its status."""
import argparse
import json
from pathlib import Path

SENDER, LOOP = 'a94f5374fce5edbc8e2a8697c15331677e6ebf0b', 'be7c43a580000000000000000000000000000001'
GAS, JUMPDEST, JUMPI, INVALID = 0x5a, 0x5b, 0x57, 0xfe
KECCAK256, MSTORE, POP, RETURNDATASIZE, ISZERO, STATICCALL = 0x20, 0x52, 0x50, 0x3d, 0x15, 0xfa


def word(value):
    return value.to_bytes(32, 'big')


def push(value):
    data = value.to_bytes(max(1, (value.bit_length() + 7) // 8), 'big')
    return bytes([0x5f + len(data)]) + data


def store(data):
    """Store `data` from memory offset 0, its length rounded up to whole words."""
    data = data + bytes(-len(data) % 32)
    code = b''
    for offset in range(0, len(data), 32):
        code += b'\x7f' + data[offset:offset + 32] + push(offset) + bytes([MSTORE])
    return code


def call(address, length, output):
    """STATICCALL `address` on the first `length` bytes of memory."""
    fail = b'\x61\xff\xff'  # placeholder for the INVALID label, patched by `program`.
    return (push(output) + push(1 << 16) + push(length) + push(0) + push(address) + bytes([GAS, STATICCALL, ISZERO])
            + fail + bytes([JUMPI, RETURNDATASIZE, ISZERO]) + fail + bytes([JUMPI]))


def program(runs, setup, body):
    # setup; PUSH2 runs; JUMPDEST; body; PUSH1 1; SWAP1; SUB; DUP1; PUSH2 loop; JUMPI; STOP; JUMPDEST; INVALID
    loop = len(setup) + 3
    tail = bytes([0x60, 1, 0x90, 0x03, 0x80, 0x61, loop >> 8, loop & 255, JUMPI, 0x00])
    fail = loop + 1 + len(body) + len(tail)
    body = body.replace(b'\x61\xff\xff', bytes([0x61, fail >> 8, fail & 255]))
    return setup + bytes([0x61, runs >> 8, runs & 255, JUMPDEST]) + body + tail + bytes([JUMPDEST, INVALID])


def p256_signature():
    """A valid secp256r1 signature, computed here to keep the fixture checkable."""
    p = 2**256 - 2**224 + 2**192 + 2**96 - 1
    n = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
    g = (0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296,
         0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5)

    def add(a, b):
        if a is None or b is None:
            return a or b
        if a[0] == b[0] and (a[1] + b[1]) % p == 0:
            return None
        slope = (3 * a[0] ** 2 - 3) * pow(2 * a[1], -1, p) if a == b else (b[1] - a[1]) * pow(b[0] - a[0], -1, p)
        x = (slope * slope - a[0] - b[0]) % p
        return x, (slope * (a[0] - x) - a[1]) % p

    def mul(k, point):
        result = None
        while k:
            result = add(result, point) if k & 1 else result
            point, k = add(point, point), k >> 1
        return result

    key, nonce, digest = 0x1234567, 0x89abcde, 0xbb5a52f42f9c9261ed4361f59422a1e30036e7c32b270c8807a419feca605023
    public, r = mul(key, g), mul(nonce, g)[0] % n
    s = pow(nonce, -1, n) * (digest + r * key) % n
    return b''.join(map(word, [digest, r, s, *public]))


def blake2f_input(rounds):
    iv = [0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
          0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179]
    iv[0] ^= 0x01010040
    state = b''.join(value.to_bytes(8, 'little') for value in iv)
    return rounds.to_bytes(4, 'big') + state + b'abc'.ljust(128, b'\0') + (3).to_bytes(16, 'little') + b'\x01'


G1 = word(1) + word(2)
G2 = b''.join(map(word, [
    11559732032986387107991004021392285783925812861821192530917403151452391805634,
    10857046999023057135944570762232829481370756359578518086990519993285655852781,
    4082367875863433681332203403145435568316851327593401208105741076214120093531,
    8495653923123431417604973247489272438418190587263600148770280649306958101930]))
BN254_P = 21888242871839275222246405745257275088696311157297823662689037894645226208583
SCALAR = word(2**255 - 19)
BLS_G1 = bytes(16) + (0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb).to_bytes(48, 'big') \
    + bytes(16) + (0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1).to_bytes(48, 'big')
ECRECOVER = b''.join(map(word, [
    0x456e9aea5e197a1f1af7a3e85a3212fa4049a3ba34c2289b4c860fc0b0c64ef3, 28,
    0x9242685bf161793cc25603c231bc2f568eb630ea16aa137d2664ac8038825608,
    0x4f8ae3bd7535248d0bd448298cc2e2071e56992d0774dc340c368ae950852ada]))
MODEXP = b''.join(map(word, [32, 32, 32, 3, 2**255 - 19, BN254_P]))
BLAKE2F = blake2f_input(1000)

# name: (runs, memory, loop body)
CASES = {
    'keccak_32': (20000, bytes(32), push(32) + push(0) + bytes([KECCAK256, POP])),
    'keccak_1k': (2000, bytes(1024), push(1024) + push(0) + bytes([KECCAK256, POP])),
    'ecrecover': (200, ECRECOVER, call(1, 128, 32)),
    'sha256_1k': (2000, bytes(1024), call(2, 1024, 32)),
    'modexp': (200, MODEXP, call(5, len(MODEXP), 32)),
    'ecadd': (2000, G1 + G1, call(6, 128, 64)),
    'ecmul': (200, G1 + SCALAR, call(7, 96, 64)),
    'ecpairing': (20, G1 + G2, call(8, 192, 32)),
    'blake2f': (200, BLAKE2F, call(9, len(BLAKE2F), 64)),
    'bls_g1add': (500, BLS_G1 + BLS_G1, call(0x0b, 256, 128)),
    'bls_g1msm': (20, BLS_G1 + SCALAR, call(0x0c, 160, 128)),
    'p256verify': (100, p256_signature(), call(0x100, 160, 32)),
}


def state_test(runs, memory, body):
    code = program(runs, store(memory), body)
    return {
        '_info': {'labels': {'0': f'n{runs}'}},
        'env': {'currentBaseFee': '0x01', 'currentCoinbase': '0x' + SENDER, 'currentDifficulty': '0x01',
                'currentGasLimit': '0x3b9aca00', 'currentNumber': '0x01',
                'currentRandom': '0x' + '00' * 31 + '01', 'currentTimestamp': '0x61a8d289'},
        'post': {'London': [{'indexes': {'data': 0, 'gas': 0, 'value': 0},
                             'logs': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'}]},
        'pre': {'0x' + SENDER: {'balance': '0x3b9aca00', 'code': '0x', 'nonce': '0x00', 'storage': {}},
                '0x' + LOOP: {'balance': '0x00', 'code': '0x' + code.hex(), 'nonce': '0x00', 'storage': {}}},
        'transaction': {'data': ['0x'], 'gasLimit': ['0x3b9aca00'], 'gasPrice': '0x01', 'nonce': '0x00',
                        'sender': '0x' + SENDER, 'to': '0x' + LOOP, 'value': ['0x00']},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path, help='directory to write the state tests to')
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    for name, case in CASES.items():
        (out / f'{name}.json').write_text(json.dumps({name: state_test(*case)}, indent=1))


if __name__ == '__main__':
    main()
