// Relinked into the CLI for RETURN of 65,537 bytes. Its memory and output
// buffers each request 131,072 bytes, larger than the frame/state descriptors.
// FAIL_AT selects memory failure (1), output failure (2), or success (0).
// The journal fixture uses FAIL_AT=1 and WATCH_SIZE=100352 to check atomic
// growth failure and undo; the logs fixture watches entry and blob-hash growth.
// The accounts fixture uses all three settings for code replacement and release.
// WATCH_MIN additionally watches every allocation of at least that many bytes;
// the calls fixture uses it to count child frame boxes.
#define _DEFAULT_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#ifndef WATCH_SIZE
#define WATCH_SIZE 131072
#endif
#ifndef WATCH_SIZE_EXTRA
#define WATCH_SIZE_EXTRA 0
#endif
#ifndef SUCCESS_ALLOCS
#define SUCCESS_ALLOCS 2
#endif

static unsigned attempts;
static unsigned allocations;
static unsigned releases;
static unsigned failures;

typedef union {
    max_align_t alignment;
    struct { size_t extent; int watched; } info;
} Header;

void *malloc(size_t size) {
    int watched = size == WATCH_SIZE || (WATCH_SIZE_EXTRA != 0 && size == WATCH_SIZE_EXTRA);
#ifdef WATCH_MIN
    watched = watched || size >= WATCH_MIN;
#endif
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
    unsigned expected = FAIL_AT ? FAIL_AT - 1 : SUCCESS_ALLOCS;
    if (attempts != (FAIL_AT ? FAIL_AT : SUCCESS_ALLOCS) ||
        failures != (FAIL_AT ? 1 : 0) ||
        allocations != expected || releases != expected) _Exit(101);
}
