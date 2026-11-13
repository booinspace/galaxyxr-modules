import test from 'node:test';
import assert from 'node:assert/strict';
import {readEyePose, readEyeActionEvent, readEyeActionBatch, isPinnedInfo, installImmersivePins} from '../scripts/curvature-pins-agent.mjs';

function pose() {
    const data = Buffer.alloc(96);
    data[0x55] = data[0x28] = 1;
    data.writeFloatLE(1, 0x44);
    const at = offset => ({isNull: () => false, add: delta => at(offset + delta),
        readU8: () => data.readUInt8(offset), readFloat: () => data.readFloatLE(offset)});
    return {data, pointer: at(0)};
}
test('eye reader uses a live gaze pose and preserves the source memory', () => {
    const f = pose(), before = Buffer.from(f.data);
    assert.deepEqual(readEyePose(f.pointer), [0, 0, 0, -0, -0, -1]);
    assert.deepEqual(f.data, before);
    f.data.writeFloatLE(Math.SQRT1_2, 0x3c);
    f.data.writeFloatLE(Math.SQRT1_2, 0x44);
    const ray = readEyePose(f.pointer);
    assert.ok(Math.abs(ray[3] + 1) < 1e-6);
    assert.ok(Math.abs(ray[5]) < 1e-6);
});
test('absent, inactive, non-finite and malformed poses never become gaze rays', () => {
    const f = pose();
    f.data[0x55] = 0; assert.equal(readEyePose(f.pointer), null);
    f.data[0x55] = 1; f.data[0x28] = 0; assert.equal(readEyePose(f.pointer), null);
    f.data[0x28] = 1; f.data.writeFloatLE(NaN, 0x2c); assert.equal(readEyePose(f.pointer), null);
    f.data.writeFloatLE(0, 0x2c); f.data.writeFloatLE(0, 0x44); assert.equal(readEyePose(f.pointer), null);
    assert.equal(readEyePose({isNull: () => true}), null);
});

function eyeEventFixture() {
    const memory = Buffer.alloc(4096), event = 128, buckets = 512, aim = buckets + 0x80;
    function pointer(at) {
        return {address: at, add: delta => pointer(at + delta), isNull: () => at === 0,
            compare: other => Math.sign(at - other.address), sub: other => ({toInt32: () => at - other.address}),
            readU8: () => memory.readUInt8(at), readS16: () => memory.readInt16LE(at),
            readU32: () => memory.readUInt32LE(at), readFloat: () => memory.readFloatLE(at),
            readU64: () => ({toNumber: () => Number(memory.readBigUInt64LE(at))}),
            readPointer: () => pointer(Number(memory.readBigUInt64LE(at))),
            readUtf8String: length => memory.toString('utf8', at, at + length)};
    }
    function text(at, value) {
        memory.fill(0, at, at + 24);
        memory.writeUInt8(value.length * 2, at);
        memory.write(value, at + 1);
    }
    text(event, 'eye');
    memory.writeBigUInt64LE(BigInt(buckets), event + 0x50);
    memory.writeBigUInt64LE(2n, event + 0x58);
    memory.writeInt16LE(-1, buckets + 4);
    text(aim + 8, 'aim');
    pose().data.copy(memory, aim + 0x20, 0, 0x58);
    memory.writeUInt32LE(4, aim + 0x78);
    return {memory, event, aim, text, at: pointer, pointer: pointer(event)};
}
test('legacy eye input reads eye/aim without modifying the native event', () => {
    const f = eyeEventFixture(), before = Buffer.from(f.memory);
    assert.deepEqual(readEyeActionEvent(f.pointer), {ray: [0, 0, 0, -0, -0, -1]});
    assert.deepEqual(f.memory, before);
    f.text(f.event, 'hand');
    assert.equal(readEyeActionEvent(f.pointer), null);
    f.text(f.event, 'eye');
    f.text(f.aim + 8, 'grip');
    assert.deepEqual(readEyeActionEvent(f.pointer), {ray: null});
});
test('legacy eye input rejects missing poses, wrong variants and oversized tables', () => {
    const f = eyeEventFixture();
    f.memory[f.aim + 0x20 + 0x55] = 0;
    assert.deepEqual(readEyeActionEvent(f.pointer), {ray: null});
    f.memory.writeUInt32LE(1, f.aim + 0x78);
    assert.throws(() => readEyeActionEvent(f.pointer), /action type/);
    f.memory.writeBigUInt64LE(257n, f.event + 0x58);
    assert.throws(() => readEyeActionEvent(f.pointer), /action table/);
    f.memory.writeBigUInt64LE(0n, f.event + 0x50);
    assert.throws(() => readEyeActionEvent(f.pointer), /action table/);
});
test('batch reader finds eyes after other devices and bounds native vector reads', () => {
    const f = eyeEventFixture(), header = 64;
    f.memory.copy(f.memory, 256, 128, 256);
    f.text(f.event, 'hand');
    f.memory.writeBigUInt64LE(128n, header);
    f.memory.writeBigUInt64LE(384n, header + 8);
    const before = Buffer.from(f.memory);
    assert.deepEqual(readEyeActionBatch(f.at(header)), {ray: [0, 0, 0, -0, -0, -1], pinching: false});
    assert.deepEqual(f.memory, before);
    f.text(f.event + 0x18, '/user/hand/left');
    f.memory.writeBigUInt64LE(1024n, f.event + 0x50);
    f.memory.writeBigUInt64LE(2n, f.event + 0x58);
    f.text(1032, 'grip');
    pose().data.copy(f.memory, 1056, 0, 0x58);
    f.memory.writeUInt32LE(4, 1024 + 0x78);
    f.text(1024 + 0x80 + 8, 'pinch_gesture');
    f.memory[1024 + 0x80 + 0x20 + 0x28] = 1;
    f.memory.writeFloatLE(.9, 1024 + 0x80 + 0x20 + 0x2c);
    f.memory.writeUInt32LE(1, 1024 + 0x80 + 0x78);
    assert.equal(readEyeActionBatch(f.at(header)).pinching, true);
    f.memory.writeFloatLE(2, 1024 + 0x80 + 0x20 + 0x2c);
    assert.equal(readEyeActionBatch(f.at(header)).pinching, false);
    f.memory.writeBigUInt64LE(129n, header + 8);
    assert.throws(() => readEyeActionBatch(f.at(header)), /event stride/);
    f.memory.writeBigUInt64LE(128n + 65n * 128n, header + 8);
    assert.throws(() => readEyeActionBatch(f.at(header)), /batch range/);
    f.memory.writeBigUInt64LE(0n, header);
    f.memory.writeBigUInt64LE(0n, header + 8);
    assert.equal(readEyeActionBatch(f.at(header)), null);
});
function info(mode = 4, marked = true, user = 0) {
    return {xrDesktopMode: {value: mode}, userId: {value: user},
        isVisible() { throw new Error('Field/method collision: do not call this'); },
        isVisibleRequested() { throw new Error('Field/method collision: do not call this'); },
        _isVisible: {value: true}, _isVisibleRequested: {value: true},
        baseIntent: {value: {hasCategory: name => {
            assert.equal(name, 'boo.puppy.gxr.PINNED_OVERLAY');
            return marked;
        }}}, taskId: {value: 42}, $dispose() {}};
}
test('only explicitly marked primary-user overlay tasks receive changes', () => {
    assert.equal(isPinnedInfo(info()), true);
    for (const other of [null, info(1), info(2), info(3), info(4, false), info(4, true, 10)]) {
        assert.equal(isPinnedInfo(other), false);
    }
});
function fixture() {
    const hooks = [], queued = [], calls = [], logs = [];
    let permitted = true, controllerRestored = false, keyguard = false;
    const method = stock => {
        const hook = {implementation: null, call: (owner, ...args) => stock.call(owner, ...args)};
        hooks.push(hook); return {overload: () => hook};
    };
    const director = {$dispose() {}, windowDecorByTaskId: {value: {get: () => null}},
        onTaskOpening: () => calls.push('caption'), destroyWindowDecoration: () => calls.push('destroy')};
    const Director = {$className: 'Director', shouldNotHaveWindowDecor: method(() => 'stock-exclusion')};
    const Decoration = {canShowDecor: method(() => 'stock-caption')};
    const Overlay = {overlayTaskRepository: {value: {}}, handleNewOverlayTask: method(() => 'stock-appear'),
        handleOverlayTaskInfoUpdate: method(() => 'stock-change'), cleanupTask: method(() => 'stock-cleanup')};
    const Runtime = {$className: 'Runtime',
        computeXrRuntimeLayerVisibility: method((sysui, overlay, immersive, keyguard) => sysui || overlay || !immersive || keyguard)};
    const controller = {$dispose() {}, add: id => calls.push('add:' + id),
        remove: id => calls.push('remove:' + id), updateInfo() {},
        bindCaptionOwner: () => calls.push('bind-owner'),
        bindRuntime: () => calls.push('bind-runtime'), bindOverlayRepository() {},
        isBackdropOverridden: () => true, wantsPinPointer: () => true,
        setRuntimeState: (...args) => calls.push(args),
        destroyCaption: (owner, value) => queued.push(() => owner.destroyWindowDecoration(value)),
        pulse() {}, getError: () => '',
        getStatus: () => 'samples=0', getRuntimeStatus: () => 'focus=stock', shutdown() { calls.push('shutdown'); },
        isRestored: () => controllerRestored};
    const classes = {
        'com.android.wm.shell.windowdecor.XrCaptionWindowDecorDirector': Director,
        'com.android.wm.shell.windowdecor.XrCaptionWindowDecoration': Decoration,
        'com.android.wm.shell.windowdecor.XrWindowDecoration': {relayout: method(() => {})},
        'com.android.systemui.xr.wm.shell.overlay.OverlayTaskControllerImpl': Overlay,
        'com.android.systemui.xr.cpm.XrRuntimeLayer': Runtime,
        'com.android.systemui.xr.spatial.impl.TaskSubspaceImpl': {},
        'android.view.SurfaceControl$Transaction': {$new: () => ({
            apply: () => calls.push('apply'), close: () => calls.push('close'), $dispose() {}})},
    };
    const Java = {use: name => { assert.ok(classes[name], name); return classes[name]; },
        retain: value => value, cast: value => value, perform: fn => fn(),
        scheduleOnMainThread() { throw new Error('Caption cleanup must use its actual owner'); },
        choose: (name, callbacks) => { callbacks.onMatch(name === 'Director' ? director : {}); callbacks.onComplete(); }};
    const previous = console.log; console.log = value => logs.push(value);
    let result;
    try { result = installImmersivePins(Java, {use: () => ({$new: () => controller,
        isTaskVisible: value => value._isVisible.value && value._isVisibleRequested.value})}, () => permitted, () => 0); }
    finally { console.log = previous; }
    return {result, hooks, calls, Director, Decoration, Overlay, Runtime,
        guard: value => { permitted = value; }, keyguard: value => { keyguard = value; },
        decor: {getKeyguardShowing: () => keyguard},
        flush() { while (queued.length) queued.shift()(); }, restore() { controllerRestored = true; }};
}
test('caption override retains keyguard, user minimise and unmarked stock behavior', () => {
    const f = fixture(), exclude = f.Director.shouldNotHaveWindowDecor.overload();
    const show = f.Decoration.canShowDecor.overload();
    assert.equal(exclude.implementation.call({}, info()), false);
    assert.equal(show.implementation.call(f.decor, info()), true);
    const hidden = info(); hidden._isVisibleRequested.value = false;
    assert.equal(show.implementation.call(f.decor, hidden), false);
    f.keyguard(true); assert.equal(show.implementation.call(f.decor, info()), false);
    assert.equal(exclude.implementation.call({}, info(1)), 'stock-exclusion');
    f.guard(false);
    assert.equal(show.implementation.call(f.decor, info()), 'stock-caption');
    f.guard(true);
    assert.equal(f.Overlay.handleNewOverlayTask.overload().implementation.call(f.Overlay, info(3), null, null), 'stock-appear');
    f.result.stop(); f.flush(); assert.equal(f.result.isRestored(), false);
    f.restore(); assert.equal(f.result.isRestored(), true);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
});
test('runtime observer preserves stock visibility and passes all protection flags unchanged', () => {
    const f = fixture(), visibility = f.Runtime.computeXrRuntimeLayerVisibility.overload();
    assert.ok(f.calls.includes('bind-runtime'));
    for (let mask = 0; mask < 16; mask++) {
        const args = [1, 2, 4, 8].map(bit => (mask & bit) !== 0);
        const expected = args[0] || args[1] || !args[2] || args[3];
        assert.equal(visibility.implementation.call({}, ...args), expected);
        assert.deepEqual(f.calls.at(-1), [...args, expected]);
    }
    f.result.stop(); f.flush();
});

test('marked overlay appearance owns one caption and eye hook, then releases both on task cleanup', () => {
    const previousProcess = globalThis.Process, previousInterceptor = globalThis.Interceptor;
    let eyeHooks = 0, detached = 0;
    const address = {equals: other => other === address, readU32: () => 0xd503233f,
        add: offset => { assert.equal(offset, 4); return {readU32: () => 0xa9ba7bfd}; }};
    globalThis.Process = {getModuleByName: name => {
        assert.equal(name, 'libspaceflinger_jni_vulkan.so');
        return {base: {add: offset => { assert.equal(offset, 0x4d9e5a0); return address; }},
            getExportByName: () => address};
    }};
    globalThis.Interceptor = {attach: target => {
        assert.equal(target, address); eyeHooks++;
        return {detach() { detached++; }};
    }};
    const f = fixture();
    try {
        const appeared = f.Overlay.handleNewOverlayTask.overload();
        const subspace = {getCpmNodeTree: () => ({})};
        assert.equal(appeared.implementation.call(f.Overlay, info(), {}, subspace), 'stock-appear');
        assert.equal(eyeHooks, 1);
        assert.equal(f.calls.filter(call => call === 'caption').length, 1);
        assert.equal(f.calls.filter(call => call === 'apply').length, 2);
        assert.ok(f.calls.includes('add:42'));
        assert.deepEqual(f.result.getRotationTaskIds(), [42]);
        const visibility = f.Runtime.computeXrRuntimeLayerVisibility.overload();
        visibility.implementation.call({}, false, true, true, false);
        assert.equal(f.result.canGrab(), true);
        visibility.implementation.call({}, true, true, true, false);
        assert.equal(f.result.canGrab(), false);
        assert.deepEqual(f.result.getRotationTaskIds(), [42]); // Transient UI must not reset an existing pose.
        f.guard(false);
        assert.deepEqual(f.result.getRotationTaskIds(), []);
        assert.equal(f.result.canGrab(), false);
        f.guard(true);
        assert.ok(f.calls.includes('bind-owner'));
        assert.equal(f.Overlay.handleOverlayTaskInfoUpdate.overload().implementation.call(
            {overlayTaskRepository: {value: {}}}, info()), 'stock-change');
        appeared.implementation.call(f.Overlay, info(), {}, subspace);
        assert.equal(eyeHooks, 1);
        assert.equal(f.calls.filter(call => call === 'caption').length, 1);
        assert.equal(f.Overlay.cleanupTask.overload().implementation.call({}, 42), 'stock-cleanup');
        assert.deepEqual(f.result.getRotationTaskIds(), []);
        assert.equal(detached, 1);
        assert.ok(f.calls.includes('remove:42'));
        assert.equal(f.calls.filter(call => call === 'destroy').length, 0);
        f.flush();
        assert.equal(f.calls.filter(call => call === 'destroy').length, 1);
        assert.equal(f.calls.filter(call => call === 'close').length, 2);
    } finally {
        f.result.stop(); f.flush();
        if (previousProcess === undefined) delete globalThis.Process;
        else globalThis.Process = previousProcess;
        if (previousInterceptor === undefined) delete globalThis.Interceptor;
        else globalThis.Interceptor = previousInterceptor;
    }
});
