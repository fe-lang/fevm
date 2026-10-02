#include <stdint.h>

// Both benchmark implementations call this once per hash. The returned length
// stays opaque across translation units; no link-time optimization is enabled.
uint64_t fevm_bench_length(uint64_t value) {
    __asm__ volatile("" : "+r"(value) : : "memory");
    return value;
}
