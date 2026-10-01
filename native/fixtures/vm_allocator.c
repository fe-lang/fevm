// Relinked into the CLI for RETURN of 65,537 bytes. Its memory and output
// buffers each request 131,072 bytes, larger than the frame/state descriptors.
// FAIL_AT selects memory failure (1), output failure (2), or success (0).
// The journal fixture uses FAIL_AT=1 to check atomic growth failure and undo.
#define _DEFAULT_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

static unsigned attempts;
static unsigned allocations;
static unsigned releases;
static unsigned failures;

typedef union {
    max_align_t alignment;
    struct { size_t extent; int watched; } info;
} Header;

void *malloc(size_t size) {
    int watched = size == 131072;
    if (watched && ++attempts == FAIL_AT) {
        failures++;
        return NULL;
    }
    if (size > SIZE_MAX - sizeof(Header)) return NULL;
    size_t extent = sizeof(Header) + size;
    Header *header = mmap(NULL, extent, PROT_READ | PROT_WRITE,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (header == MAP_FAILED) return NULL;
    header->info.extent = extent;
    header->info.watched = watched;
    allocations += watched;
    memset(header + 1, 0xa5, size);
    return header + 1;
}

void free(void *pointer) {
    if (pointer == NULL) return;
    Header *header = (Header *)pointer - 1;
    releases += header->info.watched;
    munmap(header, header->info.extent);
}

__attribute__((destructor)) static void check_releases(void) {
    unsigned expected = FAIL_AT ? FAIL_AT - 1 : 2;
    if (attempts != (FAIL_AT ? FAIL_AT : 2) ||
        failures != (FAIL_AT ? 1 : 0) ||
        allocations != expected || releases != expected) _Exit(101);
}
