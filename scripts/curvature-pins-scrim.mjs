// Both exact AZJ2 setters only store s0 at self+0x44 and preserve x0.
export const PIN_SCRIM_SOURCE = `
#include <gum/guminterceptor.h>
#include <glib.h>
typedef struct { long seconds; long nanoseconds; } PinTimespec;
extern int pin_clock_gettime(int clock, PinTimespec *time);
extern void *pin_malloc(unsigned long size);
extern gpointer deadline;
extern gpointer input_deadline;
extern gint snapshots;
extern gint routed;
extern gint scrim_frames;
extern gint scrim_suppressed;
extern gpointer scrim_alpha_total;

void arm(gpointer next) {
    gssize previous = g_atomic_pointer_add(&deadline, 0);
    g_atomic_pointer_add(&deadline, (gssize) next - previous);
}
void arm_input(gpointer next) {
    gssize previous = g_atomic_pointer_add(&input_deadline, 0);
    g_atomic_pointer_add(&input_deadline, (gssize) next - previous);
}
static gboolean live(gpointer *slot) {
    gint64 until = (gint64) g_atomic_pointer_add(slot, 0);
    if (until == 0) return FALSE;
    PinTimespec time;
    return pin_clock_gettime(1, &time) == 0 && time.seconds * 1000 + time.nanoseconds / 1000000 < until;
}
void on_leave(GumInvocationContext *context) {
    if (!live(&deadline)) return;
    guint8 *renderer = gum_invocation_context_get_nth_argument(context, 0);
    if (renderer != NULL) *(float *) (renderer + 0x44) = 1.0f;
}
void scrim_enter(GumInvocationContext *context) {
    if (!live(&deadline)) return;
    float alpha = context->cpu_context->v[0].s;
    if (!(alpha >= 0.0f && alpha <= 1.0f)) return;
    g_atomic_int_add(&scrim_frames, 1);
    g_atomic_pointer_add(&scrim_alpha_total, (gssize) (alpha * 1000.0f));
    if (alpha > 0.0f) g_atomic_int_add(&scrim_suppressed, 1);
    // The fullscreen mesh is separate from the CPM layer's ScrimConfig.
    context->cpu_context->v[0].s = 0.0f;
}
void input_leave(GumInvocationContext *context) {
    if (!live(&deadline) || !live(&input_deadline)) return;
    const guint8 *source = gum_invocation_context_get_return_value(context);
    if (source == NULL || source[0x38] > 1) return;
    gpointer *copy = gum_invocation_context_get_listener_thread_data(context, sizeof(gpointer));
    if (*copy == NULL) {
        if (g_atomic_int_add(&snapshots, 1) >= 32) { g_atomic_int_add(&snapshots, -1); return; }
        *copy = pin_malloc(0x54);
        if (*copy == NULL) { g_atomic_int_add(&snapshots, -1); return; }
    }
    // shortcut: 32 per-thread POD copies survive unhook; revisit if same-process reinjection is supported.
    guint8 *local = *copy;
    for (guint i = 0; i < 0x54; i++) local[i] = source[i];
    local[0x38] = 0;
    gum_invocation_context_replace_return_value(context, local);
    g_atomic_int_add(&routed, 1);
}
gint get_routed(void) { return g_atomic_int_add(&routed, 0); }
gint get_scrim_frames(void) { return g_atomic_int_add(&scrim_frames, 0); }
gint get_scrim_suppressed(void) { return g_atomic_int_add(&scrim_suppressed, 0); }
gint get_scrim_alpha(void) {
    gint frames = g_atomic_int_add(&scrim_frames, 0);
    return frames > 0 ? g_atomic_pointer_add(&scrim_alpha_total, 0) / frames : 0;
}
`;

export function installPinnedScrim(nowMs) {
    if (Process.arch !== 'arm64' || Process.pointerSize !== 8) throw new Error('AZJ2 scrim ABI mismatch');
    const backend = Process.getModuleByName('libspaceflinger_jni_vulkan.so');
    const targets = [
        ['_ZN12spaceflinger15SurfaceRenderer19SetTargetScrimAlphaEf', 0x4e28710,
            [0xd503245f, 0xbd004400, 0xd65f03c0], {onLeave: 'on_leave'}],
        ['_ZN12spaceflinger20MultiSurfaceRenderer19SetTargetScrimAlphaEf', 0x4e18e10,
            [0xd503245f, 0xbd004400, 0xd65f03c0], {onLeave: 'on_leave'}],
        ['_ZNK12spaceflinger20SystemInputInfoStore3getEv', 0x4dbadac,
            [0xd503245f, 0x9100e000, 0xd65f03c0], {onLeave: 'input_leave'}],
        ['_ZN12spaceflinger5Scrim8SetAlphaEf', 0x4e2c990,
            [0xd503233f, 0xd10603ff, 0xfd0093ec, 0x6d132beb], {onEnter: 'scrim_enter'}],
    ].map(([symbol, offset, words, callbacks]) => {
        const address = backend.getExportByName(symbol);
        if (!address.equals(backend.base.add(offset)) || words.some((word, i) => address.add(i * 4).readU32() !== word)) {
            throw new Error('AZJ2 scrim setter mismatch: ' + symbol);
        }
        return {address, callbacks};
    });
    const deadline = Memory.alloc(Process.pointerSize);
    deadline.writePointer(ptr(0));
    const inputState = Memory.alloc(16);
    inputState.writePointer(ptr(0));
    inputState.add(8).writeS32(0); inputState.add(12).writeS32(0);
    const scrimState = Memory.alloc(16);
    scrimState.writeS32(0); scrimState.add(4).writeS32(0); scrimState.add(8).writePointer(ptr(0));
    const module = new CModule(PIN_SCRIM_SOURCE, {deadline,
        input_deadline: inputState, snapshots: inputState.add(8), routed: inputState.add(12),
        scrim_frames: scrimState, scrim_suppressed: scrimState.add(4), scrim_alpha_total: scrimState.add(8),
        pin_malloc: Module.getGlobalExportByName('malloc'),
        pin_clock_gettime: Module.getGlobalExportByName('clock_gettime')});
    const arm = new NativeFunction(module.arm, 'void', ['pointer']);
    const armInput = new NativeFunction(module.arm_input, 'void', ['pointer']);
    const routed = new NativeFunction(module.get_routed, 'int', []);
    const scrimFrames = new NativeFunction(module.get_scrim_frames, 'int', []);
    const scrimSuppressed = new NativeFunction(module.get_scrim_suppressed, 'int', []);
    const scrimAlpha = new NativeFunction(module.get_scrim_alpha, 'int', []);
    const hooks = [];
    let stopped = false;
    try {
        for (const target of targets) hooks.push(Interceptor.attach(target.address,
            Object.fromEntries(Object.entries(target.callbacks).map(([phase, name]) => [phase, module[name]]))));
    } catch (error) {
        try { arm(ptr(0)); }
        finally { try { armInput(ptr(0)); } finally { for (const hook of hooks) hook.detach(); } }
        throw error;
    }
    return {
        // Raw function pointers retain neither executable code nor its imported storage.
        nativeModule: module,
        deadline,
        inputState,
        scrimState,
        setAllowed(allowed) {
            if (stopped) return;
            try { arm(ptr(allowed ? Math.floor(nowMs() + 1000) : 0)); }
            finally { if (!allowed) armInput(ptr(0)); }
        },
        setInputAllowed(allowed) {
            if (!stopped) armInput(ptr(allowed ? Math.floor(nowMs() + 1000) : 0));
        },
        getInputRouting: () => stopped ? 0 : routed(),
        getScrimDiagnostics: () => ({frames: scrimFrames(), suppressed: scrimSuppressed(), meanAlpha: scrimAlpha() / 1000}),
        stop() {
            if (stopped) return;
            stopped = true;
            try { arm(ptr(0)); }
            finally { try { armInput(ptr(0)); } finally { for (const hook of hooks) hook.detach(); } }
        },
    };
}
