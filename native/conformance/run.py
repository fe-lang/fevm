#!/usr/bin/env python3
"""Run Ethereum execution-spec state tests (Osaka) against native FeVM."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FORK = 'Osaka'
# BPO2's, for fixtures without a blob schedule.
BLOB_BASE_FEE_UPDATE_FRACTION = 11684671
# Execution statuses defined by the EVM (see ingots/evm/src/constants.fe);
# every other driver status is a host failure.
EVM_STATUSES = {0: 'success', 19: 'revert', 10: 'stack_underflow', 11: 'stack_overflow',
                15: 'out_of_gas', 16: 'invalid_jump', 17: 'invalid_opcode', 18: 'return_data_oob',
                23: 'static_write', 24: 'code_prefix', 25: 'precompile_failure', 27: 'address_collision'}
HOST_STATUSES = {21: 'host_allocation', 26: 'balance_overflow'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return int(value, 16) if isinstance(value, str) else int(value)


def be(value, width):
    return number(value).to_bytes(width, 'big')


def blob_base_fee(excess, fraction):
    # EIP-4844 fake_exponential(MIN_BLOB_GASPRICE, excess, UPDATE_FRACTION).
    output, accumulator, i = 0, fraction, 1
    while accumulator > 0:
        output += accumulator
        accumulator = accumulator * excess // (fraction * i)
        i += 1
    return output // fraction


def blob(value):
    return bytes.fromhex(value[2:] if value.startswith('0x') else value)


def tx_kind(transaction):
    if 'authorizationList' in transaction:
        return 4
    if 'blobVersionedHashes' in transaction:
        return 3
    if 'maxFeePerGas' in transaction:
        return 2
    return 1 if 'accessLists' in transaction else 0


def encode(test, indexes):
    """The driver's binary case format; integers and lengths are big endian."""
    env, tx = test['env'], test['transaction']
    out = bytearray([1])
    out += be(env['currentCoinbase'], 20)
    out += be(env['currentNumber'], 32)
    out += be(env['currentTimestamp'], 32)
    out += be(env.get('currentRandom', env.get('currentDifficulty', '0x0')), 32)
    out += be(env['currentGasLimit'], 32)
    out += be(env.get('currentBaseFee', '0x0'), 32)
    schedule = test.get('config', {}).get('blobSchedule', {}).get(FORK, {})
    fraction = number(schedule.get('baseFeeUpdateFraction', BLOB_BASE_FEE_UPDATE_FRACTION))
    out += blob_base_fee(number(env.get('currentExcessBlobGas', '0x0')), fraction).to_bytes(32, 'big')
    out += be(test.get('config', {}).get('chainid', '0x1'), 32)
    pre = test['pre']
    out += len(pre).to_bytes(4, 'big')
    for address, account in pre.items():
        code = blob(account.get('code', '0x'))
        storage = [(slot, value) for slot, value in account.get('storage', {}).items() if number(value)]
        out += be(address, 20) + be(account.get('balance', '0x0'), 32) + be(account.get('nonce', '0x0'), 32)
        out += len(code).to_bytes(4, 'big') + code + len(storage).to_bytes(4, 'big')
        for slot, value in storage:
            out += be(slot, 32) + be(value, 32)
    kind = tx_kind(tx)
    out += bytes([kind]) + be(tx['sender'], 20)
    creates = tx['to'] in ('', '0x')
    out += bytes([1 if creates else 0]) + (bytes(20) if creates else be(tx['to'], 20))
    out += be(tx['nonce'], 32) + be(tx['gasLimit'][indexes['gas']], 8)
    out += be(tx['maxFeePerGas'] if kind >= 2 else tx['gasPrice'], 32)
    out += be(tx.get('maxPriorityFeePerGas', '0x0'), 32) + be(tx.get('maxFeePerBlobGas', '0x0'), 32)
    out += be(tx['value'][indexes['value']], 32)
    data = blob(tx['data'][indexes['data']])
    out += len(data).to_bytes(4, 'big') + data
    access = (tx.get('accessLists') or [None] * (indexes['data'] + 1))[indexes['data']] or []
    out += len(access).to_bytes(4, 'big')
    for entry in access:
        out += be(entry['address'], 20) + len(entry['storageKeys']).to_bytes(4, 'big')
        out += b''.join(be(key, 32) for key in entry['storageKeys'])
    hashes = tx.get('blobVersionedHashes', [])
    out += len(hashes).to_bytes(4, 'big') + b''.join(be(value, 32) for value in hashes)
    return bytes(out)


def expected_state(alloc):
    return {number(address): (number(account.get('balance', '0x0')), number(account.get('nonce', '0x0')),
                              blob(account.get('code', '0x')).hex(),
                              {number(k): number(v) for k, v in account.get('storage', {}).items() if number(v)})
            for address, account in alloc.items()}


def observed_state(result):
    accounts = {int(a, 16): (int(b, 16), int(n, 16), code[2:], {}) for a, b, n, code in result['accounts']}
    for address, slot, value in result['storage']:
        # Storage without an account record is stale and shows up as a difference.
        if int(value, 16):
            accounts.setdefault(int(address, 16), (0, 0, '', {}))[3][int(slot, 16)] = int(value, 16)
    return accounts


def state_difference(expected, observed):
    lines = []
    for address in sorted(expected.keys() | observed.keys()):
        want, got = expected.get(address), observed.get(address)
        if want == got:
            continue
        if want is None or got is None:
            lines.append(f'{address:#042x}: expected {"absent" if want is None else want}, got {"absent" if got is None else got}')
            continue
        for name, a, b in zip(('balance', 'nonce', 'code'), want, got):
            if a != b:
                lines.append(f'{address:#042x} {name}: expected {a}, got {b}')
        for slot in sorted(want[3].keys() | got[3].keys()):
            if want[3].get(slot, 0) != got[3].get(slot, 0):
                lines.append(f'{address:#042x}[{slot:#x}]: expected {want[3].get(slot, 0):#x}, got {got[3].get(slot, 0):#x}')
    return lines


def cases(fixtures, selection):
    for path in sorted(fixtures.rglob('*.json')):
        relative = path.relative_to(fixtures)
        if selection and not any(part in str(relative) for part in selection):
            continue
        for name, test in json.loads(path.read_text()).items():
            for index, post in enumerate(test.get('post', {}).get(FORK, [])):
                yield {'file': str(relative), 'name': name, 'index': index, 'test': test, 'post': post}


def check(executable, case, timeout):
    post = case['post']
    started = time.perf_counter()
    try:
        observed = subprocess.run([str(executable)], input=encode(case['test'], post['indexes']),
                                  capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'timeout', [f'exceeded {timeout} seconds'], time.perf_counter() - started
    seconds = time.perf_counter() - started
    try:
        result = json.loads(observed.stdout)
    except ValueError:
        return 'crash', [f'exit status {observed.returncode}', observed.stderr.decode(errors='replace')[-2000:]], seconds
    if 'host_error' in result:
        return 'host_error', [result['host_error']], seconds
    if observed.returncode:
        return 'crash', [f'exit status {observed.returncode}'], seconds
    status = result['status']
    if result['invalid'] == 0 and status not in EVM_STATUSES:
        return 'host_error', [HOST_STATUSES.get(status, f'status {status}')], seconds
    problems = []
    expect_invalid = 'expectException' in post
    if expect_invalid != (result['invalid'] != 0):
        problems.append(f'expected {"invalid (" + post["expectException"] + ")" if expect_invalid else "valid"}, '
                        f'got {"invalid " + str(result["invalid"]) if result["invalid"] else "valid"}')
    if result['logs_hash'] != f'0x{number(post["logs"]):064x}':
        problems.append(f'logs hash {result["logs_hash"]} != {post["logs"]}')
    problems += state_difference(expected_state(post['state']), observed_state(result))
    if problems:
        problems.insert(0, f'execution status {EVM_STATUSES.get(status, status)}, gas used {result["gas_used"]}')
        return 'failed', problems, seconds
    return 'passed', [], seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True,
                        help='state_tests directory of an execution-spec-tests fixture release')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--level', choices=['0', '1', '2'], default='2')
    parser.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument('--timeout', type=int, default=120, help='seconds per case')
    parser.add_argument('--select', nargs='*', default=[], help='run fixture paths containing any of these strings')
    parser.add_argument('--executable', type=Path, help='reuse a built driver instead of compiling one')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'fork': FORK, 'host': platform.platform(), 'fixtures': str(args.fixtures.resolve()),
              'revision': subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip(),
              'dirty': bool(subprocess.check_output(['git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=no'])),
              'level': args.level, 'select': args.select}
    executable = args.executable
    if executable is None:
        compiler = args.fe.resolve()
        report |= {'compiler_sha256': digest(compiler),
                   'compiler_version': subprocess.check_output([compiler, '--version'], text=True).strip()}
        started = time.perf_counter()
        with (out / 'build.log').open('wb') as log:
            subprocess.run([compiler, 'build', ROOT, '--ingot', 'fevm_conformance', '--backend', 'native',
                            '-O', args.level, '--out-dir', out / 'build'], stdout=log, stderr=subprocess.STDOUT,
                           check=True)
        report['build_seconds'] = time.perf_counter() - started
        executable = out / 'build' / 'fevm_conformance'
    report['executable_sha256'] = digest(executable)
    selected = list(cases(args.fixtures.resolve(), args.select))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        outcomes = list(pool.map(lambda case: check(executable, case, args.timeout), selected))
    report['seconds'] = time.perf_counter() - started
    totals, groups = Counter(), {}
    with (out / 'cases.jsonl').open('w') as rows:
        for case, (outcome, problems, seconds) in zip(selected, outcomes, strict=True):
            totals[outcome] += 1
            group = '/'.join(Path(case['file']).parts[:2])
            groups.setdefault(group, Counter())[outcome] += 1
            rows.write(json.dumps({'file': case['file'], 'name': case['name'], 'index': case['index'],
                                   'indexes': case['post']['indexes'], 'outcome': outcome,
                                   'seconds': round(seconds, 3), 'problems': problems}) + '\n')
    report |= {'cases': len(selected), 'totals': dict(totals),
               'groups': {group: dict(counts) for group, counts in sorted(groups.items())}}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['totals']))
    sys.exit(0 if totals['passed'] == len(selected) else 1)


if __name__ == '__main__':
    main()
