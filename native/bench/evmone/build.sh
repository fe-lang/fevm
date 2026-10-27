#!/bin/sh
# usage: build.sh EVMONE_SOURCE EVMONE_BUILD OUT
# Builds runner.cpp against an evmone build configured with -DEVMONE_TESTING=ON
# that has built the evmone and evmone.testutils targets.
set -eu
src=$1 build=$2 out=$3
deps=$(sed -n 's|^intx_DIR:PATH=\(.*\)/lib/cmake/intx$|\1|p' "$build/CMakeCache.txt")
c++ -std=c++20 -O3 -march=native -DNDEBUG -I"$src" -I"$src/include" -I"$src/evmc/include" -I"$src/lib" \
    -I"$deps/include" "$(dirname "$0")/runner.cpp" "$build/test/utils/libevmone.testutils.a" \
    "$build/lib/libevmone-state.a" "$build/lib/evmone_precompiles/libevmone_precompiles.a" \
    "$build/deps/src/blst/libblst.a" -L"$build/lib" -levmone -Wl,-rpath,"$build/lib" -o "$out"
