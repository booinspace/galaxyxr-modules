import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {PIN_SCRIM_SOURCE, installPinnedScrim} from '../scripts/curvature-pins-scrim.mjs';

test('native brightness override expires and touches only the verified alpha field', () => {
    const directory = mkdtempSync(join(tmpdir(), 'gxr-pin-scrim-'));
    try {
        mkdirSync(join(directory, 'gum'));
        writeFileSync(join(directory, 'glib.h'), `#include <stdint.h>
#include <stddef.h>
typedef void *gpointer; typedef intptr_t gssize; typedef int64_t gint64; typedef uint8_t guint8;
typedef int gint; typedef unsigned guint; typedef int gboolean;
#define FALSE 0
static gssize g_atomic_pointer_add(void *slot, gssize value) {
 return __atomic_fetch_add((gssize *) slot, value, __ATOMIC_SEQ_CST);
}
static gint g_atomic_int_add(gint *slot, gint value) { return __atomic_fetch_add(slot, value, __ATOMIC_SEQ_CST); }
`);
        writeFileSync(join(directory, 'gum/guminterceptor.h'), `#include <stddef.h>
typedef union { unsigned char q[16]; double d; float s; } GumArm64VectorReg;
typedef struct { GumArm64VectorReg v[32]; } GumCpuContext;
typedef struct { void *renderer; void *returned; void *copy; GumCpuContext *cpu_context; } GumInvocationContext;
static void *gum_invocation_context_get_nth_argument(GumInvocationContext *context, unsigned n) {
 return n == 0 ? context->renderer : 0;
}
static void *gum_invocation_context_get_return_value(GumInvocationContext *context) { return context->returned; }
static void gum_invocation_context_replace_return_value(GumInvocationContext *context, void *value) { context->returned = value; }
static void *gum_invocation_context_get_listener_thread_data(GumInvocationContext *context, size_t size) {
 (void) size; return &context->copy;
}
`);
        const file = join(directory, 'check.c');
        writeFileSync(file, PIN_SCRIM_SOURCE + `
#include <assert.h>
#include <string.h>
#include <stdlib.h>
gpointer deadline, input_deadline;
gint snapshots, routed;
gint scrim_frames, scrim_suppressed;
gpointer scrim_alpha_total;
static long now = 100, clock_failure;
static int malloc_failure, allocations;
static unsigned char *buffers[32];
void *pin_malloc(unsigned long size) {
 assert(size == 0x54);
 if (malloc_failure) return NULL;
 assert(allocations < 32);
 unsigned char *buffer = malloc(size + 16);
 assert(buffer != NULL); memset(buffer, 0xa5, size + 16);
 buffers[allocations++] = buffer;
 return buffer + 8;
}
int pin_clock_gettime(int clock, PinTimespec *time) {
 assert(clock == 1); time->seconds = now / 1000; time->nanoseconds = (now % 1000) * 1000000;
 return clock_failure;
}
int main(void) {
 GumCpuContext cpu; memset(&cpu, 0x5a, sizeof cpu);
 GumInvocationContext scrim = {.cpu_context = &cpu};
 cpu.v[0].s = .2f; scrim_enter(&scrim); assert(cpu.v[0].s == .2f);
 arm((gpointer) 1100); scrim_enter(&scrim); assert(cpu.v[0].s == 0);
 assert(get_scrim_frames() == 1 && get_scrim_suppressed() == 1 && get_scrim_alpha() == 200);
 for (unsigned i = 4; i < sizeof cpu; i++) assert(((unsigned char *) &cpu)[i] == 0x5a);
 scrim_enter(&scrim); assert(get_scrim_frames() == 2 && get_scrim_suppressed() == 1);
 cpu.v[0].s = 1.1f; scrim_enter(&scrim); assert(cpu.v[0].s == 1.1f && get_scrim_frames() == 2);
 cpu.v[0].s = -1.0f; scrim_enter(&scrim); assert(cpu.v[0].s == -1.0f);
 cpu.v[0].s = 0.0f / 0.0f; scrim_enter(&scrim); assert(cpu.v[0].s != cpu.v[0].s);
 cpu.v[0].s = .2f; clock_failure = 1; scrim_enter(&scrim); assert(cpu.v[0].s == .2f);
 clock_failure = 0; now = 1100; scrim_enter(&scrim); assert(cpu.v[0].s == .2f);
 now = 100; arm(0); scrim_enter(&scrim); assert(cpu.v[0].s == .2f);
 union { float aligned[32]; unsigned char bytes[128]; } renderer;
 memset(&renderer, 0x5a, sizeof renderer);
 GumInvocationContext context = {.renderer = renderer.bytes};
 float *alpha = (float *) (renderer.bytes + 0x44);
 *alpha = .3f; on_leave(&context); assert(*alpha == .3f);
 arm((gpointer) 1100); on_leave(&context); assert(*alpha == 1);
 *alpha = .3f; now = 1100; on_leave(&context); assert(*alpha == .3f);
 now = 100; arm(0); on_leave(&context); assert(*alpha == .3f);
 arm((gpointer) 1100); clock_failure = 1; on_leave(&context); assert(*alpha == .3f);
 context.renderer = 0; clock_failure = 0; on_leave(&context);
 for (unsigned i = 0; i < sizeof renderer; i++) if (i < 0x44 || i >= 0x48) assert(renderer.bytes[i] == 0x5a);
 unsigned char source[0x54]; memset(source, 0x5a, sizeof source); source[0x38] = 1;
 GumInvocationContext input = {.returned = source};
 input_leave(&input); assert(input.returned == source);
 arm_input((gpointer) 1100); input_leave(&input); assert(input.returned != source);
 unsigned char *copy = input.returned;
 for (unsigned i = 0; i < sizeof source; i++) assert(copy[i] == (i == 0x38 ? 0 : source[i]));
 assert(source[0x38] == 1 && get_routed() == 1);
 input.returned = source; arm_input(0); input_leave(&input); assert(input.returned == source);
 arm_input((gpointer) 1100); arm(0); input_leave(&input); assert(input.returned == source);
 arm((gpointer) 1100); clock_failure = 1; input_leave(&input); assert(input.returned == source);
 clock_failure = 0; now = 1100; input_leave(&input); assert(input.returned == source);
 now = 100; source[0x38] = 2; input_leave(&input); assert(input.returned == source);
 source[0x38] = 1; input.returned = NULL; input_leave(&input); assert(input.returned == NULL);
 GumInvocationContext other = {.returned = source};
 malloc_failure = 1; input_leave(&other); assert(other.returned == source);
 malloc_failure = 0;
 GumInvocationContext threads[32] = {0};
 for (unsigned i = 0; i < 32; i++) {
  threads[i].returned = source; input_leave(&threads[i]);
  assert((threads[i].returned != source) == (i < 31));
 }
 assert(allocations == 32);
 for (unsigned i = 0; i < sizeof source; i++) assert(source[i] == (i == 0x38 ? 1 : 0x5a));
 for (unsigned n = 0; n < 32; n++) {
  for (unsigned i = 0; i < 8; i++) assert(buffers[n][i] == 0xa5 && buffers[n][0x5c + i] == 0xa5);
  free(buffers[n]);
 }
 return 0;
}
`);
        const binary = join(directory, 'check');
        execFileSync(process.env.CC || 'cc', ['-std=c11', '-Wall', '-Wextra', '-Werror', '-I', directory, file, '-o', binary]);
        execFileSync(binary);
    } finally { rmSync(directory, {recursive: true, force: true}); }
});

test('setter hooks reject changed code and stop on failed installation or lost scope', () => {
    const names = ['Process', 'Memory', 'Module', 'CModule', 'NativeFunction', 'Interceptor', 'ptr'];
    const saved = new Map(names.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
    let mismatch = false, failAttach = false, failArm = false;
    const attached = [], detached = [], armed = [];
    class Pointer {
        constructor(value) { this.value = value; }
        add(n) { return new Pointer(this.value + n); }
        equals(other) { return this.value === other.value; }
        writePointer() { return this; }
        writeS32() { return this; }
        readU32() {
            const offset = offsets.find(value => this.value >= value && this.value < value + words.get(value).length * 4);
            const index = (this.value - offset) / 4;
            return mismatch && index === 1 ? 0 : words.get(offset)[index];
        }
    }
    const offsets = [0x4e28710, 0x4e18e10, 0x4dbadac, 0x4e2c990];
    const words = new Map(offsets.map((offset, i) => [offset, i === 3 ?
        [0xd503233f, 0xd10603ff, 0xfd0093ec, 0x6d132beb] :
        [0xd503245f, i === 2 ? 0x9100e000 : 0xbd004400, 0xd65f03c0]]));
    try {
        globalThis.ptr = value => new Pointer(Number(value));
        globalThis.Process = {arch: 'arm64', pointerSize: 8, getModuleByName: () => ({base: ptr(0),
            getExportByName: symbol => ptr(offsets[symbol.includes('SystemInputInfoStore') ? 2 : symbol.includes('5Scrim') ? 3 : symbol.includes('MultiSurface') ? 1 : 0])})};
        globalThis.Memory = {alloc: () => ptr(0)};
        globalThis.Module = {getGlobalExportByName: () => ptr(0)};
        globalThis.CModule = class { constructor() {
            this.arm = ptr(1); this.on_leave = ptr(2); this.arm_input = ptr(3); this.get_routed = ptr(4); this.input_leave = ptr(5);
            this.scrim_enter = ptr(6); this.get_scrim_frames = ptr(7);
            this.get_scrim_suppressed = ptr(8); this.get_scrim_alpha = ptr(9);
        } };
        globalThis.NativeFunction = function (target) { return value => {
            if ([4, 7, 8, 9].includes(target.value)) return 0;
            if (failArm) throw new Error('fixture native arm failure');
            armed.push(value.value);
        }; };
        globalThis.Interceptor = {attach(target, callbacks) {
            if (failAttach && attached.length === 1) throw new Error('fixture attach failure');
            assert.deepEqual(Object.keys(callbacks), [target.value === offsets[3] ? 'onEnter' : 'onLeave']);
            attached.push(target.value); return {detach: () => detached.push(target.value)};
        }};
        mismatch = true;
        assert.throws(() => installPinnedScrim(() => 100), /setter mismatch/);
        assert.equal(attached.length, 0);
        mismatch = false;
        const hook = installPinnedScrim(() => 100);
        assert.ok(hook.nativeModule instanceof globalThis.CModule, 'controller must own its executable code');
        assert.ok(hook.deadline instanceof Pointer, 'controller must own its imported mutable storage');
        assert.ok(hook.inputState instanceof Pointer, 'controller must own the writable input state');
        assert.ok(hook.scrimState instanceof Pointer, 'controller must own the writable brightness counters');
        assert.deepEqual(hook.getScrimDiagnostics(), {frames: 0, suppressed: 0, meanAlpha: 0});
        hook.setAllowed(true); assert.equal(armed.at(-1), 1100);
        hook.setInputAllowed(true); assert.equal(armed.at(-1), 1100);
        hook.setAllowed(false); assert.equal(armed.at(-1), 0);
        hook.stop(); hook.stop(); hook.setAllowed(true);
        assert.equal(armed.at(-1), 0); assert.equal(detached.length, 4);
        attached.length = 0; detached.length = 0; failAttach = true;
        assert.throws(() => installPinnedScrim(() => 100), /attach failure/);
        assert.equal(armed.at(-1), 0); assert.equal(detached.length, 1);
        attached.length = 0; detached.length = 0; failAttach = false;
        const broken = installPinnedScrim(() => 100);
        failArm = true;
        assert.throws(() => broken.stop(), /native arm failure/);
        assert.equal(detached.length, 4, 'native disarm failure must still detach every callback');
        assert.doesNotThrow(() => broken.setAllowed(true), 'a stopped controller must not call native code');
    } finally {
        for (const name of names) {
            const descriptor = saved.get(name);
            if (descriptor) Object.defineProperty(globalThis, name, descriptor);
            else delete globalThis[name];
        }
    }
});
