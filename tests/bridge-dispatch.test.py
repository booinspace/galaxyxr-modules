"""Compile the bridge's real mapping functions against a small native host fixture."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
start = source.index('  const code = `', source.index('function makeArtController (api, vm) {')) + len('  const code = `')
end = source.index('\ngpointer\nfind_replacement_method_from_quick_code', start)
code = source[start:end]
assert 'g_mutex_lock' not in code, 'ART dispatch must not block on the old mutex'
code = code.replace('#include <gum/guminterceptor.h>', '')
headers = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdio.h>
typedef void * gpointer;
typedef uintptr_t gsize;
typedef intptr_t gssize;
typedef unsigned int guint;
typedef int gboolean;
#define TRUE 1
#define FALSE 0
#define g_new(type, count) ((type *) malloc(sizeof(type) * (count)))
#define g_free free
static gssize g_atomic_pointer_add(volatile void * storage, gssize value) {
    return __atomic_fetch_add((gssize *) storage, value, __ATOMIC_SEQ_CST);
}
'''
fixture = r'''
gpointer entries;
struct Method { uint32_t klass, padding; void * quick; };
static struct Method stable, stable_value, other, other_value;
static int running, errors;
static unsigned long reads;
static void * reader(void * unused) {
    unsigned long local_reads = 0;
    while (__atomic_load_n(&running, __ATOMIC_SEQ_CST)) {
        if (get_replacement_method(&stable) != &stable_value)
            __atomic_fetch_add(&errors, 1, __ATOMIC_SEQ_CST);
        local_reads++;
    }
    __atomic_fetch_add(&reads, local_reads, __ATOMIC_SEQ_CST);
    return NULL;
}
int main(void) {
    struct Method churn, churn_value, replacement;
    pthread_t workers[4];
    init();
    set_replacement_method(&stable, &stable_value);
    set_replacement_method(&other, &other_value);
    assert(get_replacement_method(&stable) == &stable_value);
    assert(is_replacement_method(&stable_value));
    assert(translate_method(&stable_value) == &stable);
    assert(translate_method(&churn) == &churn);
    set_replacement_method(&other, &replacement);
    assert(get_replacement_method(&other) == &replacement);
    delete_replacement_method(&other);
    assert(get_replacement_method(&other) == NULL);
    assert(!is_replacement_method(&replacement));
    assert(!is_replacement_method(&other_value));
    assert(get_replacement_method(&stable) == &stable_value);
    stable.klass = 0x1234;
    stable.quick = &churn;
    synchronize_replacement_methods(offsetof(struct Method, quick), &churn, &replacement);
    assert(stable_value.klass == 0x1234);
    assert(stable.quick == &replacement);
    __atomic_store_n(&running, 1, __ATOMIC_SEQ_CST);
    for (int i = 0; i < 4; i++) assert(pthread_create(&workers[i], NULL, reader, NULL) == 0);
    for (int i = 0; i < 3000; i++) {
        set_replacement_method(&churn, &churn_value);
        delete_replacement_method(&churn);
    }
    __atomic_store_n(&running, 0, __ATOMIC_SEQ_CST);
    for (int i = 0; i < 4; i++) assert(pthread_join(workers[i], NULL) == 0);
    assert(errors == 0);
    assert(reads > 0);
    delete_replacement_method(&stable);
    assert(get_replacement_method(&stable) == NULL);
    assert(!is_replacement_method(&stable_value));
    finalize();
    printf("PASS: real dispatch mappings, replacement/deletion, GC synchronization and %lu concurrent reads\n", reads);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='gxr-dispatch-host-') as directory:
    work = Path(directory)
    (work / 'check.c').write_text(headers + code + fixture)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O2', '-pthread',
                    str(work / 'check.c'), '-o', str(work / 'check')], check=True)
    subprocess.run([str(work / 'check')], check=True, timeout=20)
