# Owned VM memory integration — unaccepted draft

The approved comparison policy is implemented: portable frame outcomes, gas and
output must agree; completed frames additionally compare stack and active memory.
Only explicitly marked simultaneous faults may differ diagnostically, and both
reasons are retained. Single-fault anchors remain checked. Operational failures
are never converted into EVM exceptional results.

The interpreter draft adopts owned native memory/output, reset and explicit
release, word-rounded expansion, gas charging before allocation, overlap-safe
MCOPY and overflow-safe source zero-fill. GAS uses the remaining frame budget.
State operations that lack transaction-dependent pricing explicitly mark gas
accounting incomplete. These changes have **not passed native acceptance**.

## Completed checks

- Four Python contract tests pass, including rejection of altered gas, output,
  machine state, unmarked reason differences and operational errors.
- Both Rust adapter tests pass; nightly formatting and strict Clippy pass.
- All 1,729 reference frames satisfy the protocol and independent specification
  anchors: the existing 1,602 frames plus 96 memory and 31 gas cases. See the
  [source identities and reference result](memory-reference-draft.json).

## Compiler prerequisite

Fe `bde32240b` spends substantial time and memory in semantic borrow checking on
the new VM. Its workspace check was stopped after 259 seconds. RSS samples were
11,708,144 KiB and 8,044,464 KiB. A CPU sample concentrates in
`BorrowState::invalidate_memory`, structural capability joins and decision-graph
interning. This occurs before native backend compilation. It is a scaling
observation, not proof of nontermination or a complete root-cause attribution.

The [small reproducer](../fixtures/buffer-borrow-scaling/two_buffers.fe) contains
two owned buffers, a writing loop, and a copying loop. It exceeds a 45-second
check timeout. Controls complete: a single-buffer loop in about 0.6 seconds,
two buffers without loops in about 8.6 seconds, and one copying loop with two
buffers in about 12.4 seconds. These are bounded diagnostic runs, not uncontended
performance measurements. [Exact records and hashes](memory-borrow-scaling-draft.json).

```sh
native/out/memory-toolchain/bin/fe check \
  native/fixtures/buffer-borrow-scaling/two_buffers.fe
```

The full sample and logs remain under `native/out/retained/`. No compiler source
or ownership rule was changed to avoid this cost. Direction has been requested
before fixing this separate compiler area, as required by the supplied AGENTS.md.
Actual VM reuse/failure tests and the full O0/O1/O2 acceptance gate remain pending.
The [last accepted foundation](owned-buffer-foundation.md) remains the baseline.
