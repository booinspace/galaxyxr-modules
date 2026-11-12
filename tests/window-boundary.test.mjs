import test from 'node:test';
import assert from 'node:assert/strict';
import {boundaryTransform, resizeHitInParent, resizeLocalFromScene, installBoundaryAlignment} from '../scripts/curvature-boundary-agent.mjs';

const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const turn = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, .2, .3, .4, 1];
const baseline = [2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, .1, .2, .01, 1];
function near(actual, expected) { actual.forEach((v, i) => assert.ok(Math.abs(v - expected[i]) < 1e-5, `${i}: ${v} != ${expected[i]}`)); }
const transformPoint = (m, p) => [0, 1, 2].map(i => m[12 + i] + p.reduce((sum, v, j) => sum + m[j * 4 + i] * v, 0));
const pitch = [1, 0, 0, 0, 0, .6, .8, 0, 0, -.8, .6, 0, 0, 0, 0, 1];
const yaw = [.6, 0, -.8, 0, 0, 1, 0, 0, .8, 0, .6, 0, 0, 0, 0, 1];
const corners = [[-.5, .5, 0], [.5, .5, 0], [-.5, -.5, 0], [.5, -.5, 0]];

test('boundary corners follow the content rotation, scale and offset', () => {
    const aligned = boundaryTransform(turn, baseline);
    near(aligned, [0, 2, 0, 0, -3, 0, 0, 0, 0, 0, 1, 0, 0, .4, .41, 1]);
    const pitch = [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1];
    const yaw = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1];
    near(boundaryTransform(pitch, baseline), [2, 0, 0, 0, 0, 0, 3, 0, 0, -1, 0, 0, .1, -.01, .2, 1]);
    near(boundaryTransform(yaw, baseline), [0, 0, -2, 0, 0, 3, 0, 0, 1, 0, 0, 0, .01, .2, -.1, 1]);
    for (const bad of [[], identity.map(() => NaN), identity.map(() => Infinity), identity.map(() => 1e8)]) {
        assert.throws(() => boundaryTransform(bad, baseline), /Invalid/);
    }
    const perspective = identity.slice(); perspective[3] = .1;
    assert.throws(() => boundaryTransform(perspective, baseline), /Invalid/);
});

test('resize classification removes all three rotation axes, scale and translation', () => {
    for (const rotation of [identity, turn, pitch, yaw, boundaryTransform(turn, boundaryTransform(pitch, yaw))]) {
        for (const scale of [.5, 1, 2]) {
            const window = rotation.map((v, i) => i < 12 ? v * scale : v);
            const aligned = boundaryTransform(window, baseline);
            for (const corner of [...corners, [0, 0, 0]]) {
                const original = transformPoint(baseline, corner);
                const hit = transformPoint(window, original);
                const expected = original.map((v, i) => v + aligned[12 + i] - baseline[12 + i]);
                near(resizeHitInParent(window, baseline, hit), expected);
            }
        }
    }
    const skew = identity.slice(); skew[4] = .2;
    const nonuniform = identity.slice(); nonuniform[0] = 2;
    const collapsed = identity.slice(); collapsed[0] = 0;
    for (const matrix of [skew, nonuniform, collapsed]) {
        assert.throws(() => resizeHitInParent(matrix, baseline, [0, 0, 0]), /Invalid/);
    }
    for (const point of [[], [NaN, 0, 0], [Infinity, 0, 0], [1e8, 0, 0]]) {
        assert.throws(() => resizeHitInParent(identity, baseline, point), /Invalid/);
    }
});

test('outward and inward resize motion use the tilted plane in every corner', () => {
    const parent = [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 1, -2, -4, 1];
    const parentInverse = [.5, 0, 0, 0, 0, .5, 0, 0, 0, 0, .5, 0, -.5, 1, 2, 1];
    const halfTurn = [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    function intersection(frame, target) {
        const origin = transformPoint(frame, [0, 0, 0]);
        const direction = [0, 1, 2].map(i => target.reduce((sum, v, k) => sum + frame[k * 4 + i] * v, 0));
        assert.ok(Math.abs(direction[2]) > 1e-6);
        const time = -origin[2] / direction[2];
        return origin.map((v, i) => v + time * direction[i]);
    }
    for (const window of [identity, turn, halfTurn, pitch, yaw, boundaryTransform(turn, boundaryTransform(pitch, yaw))]) {
        const sceneFromWindow = boundaryTransform(parent, window);
        const frame = resizeLocalFromScene(window, parentInverse);
        for (const corner of corners) for (const factor of [.8, 1.2]) {
            const start = [corner[0] * 2, corner[1] * 3, 0];
            const end = start.map(v => v * factor);
            const first = intersection(frame, transformPoint(sceneFromWindow, start));
            const last = intersection(frame, transformPoint(sceneFromWindow, end));
            // AZJ2's solver adds twice the signed local displacement to the starting dimensions.
            const size = [2, 3].map((v, i) => v + 2 * (last[i] - first[i]) * Math.sign(first[i]));
            near(size, [2 * factor, 3 * factor]);
        }
    }
    assert.throws(() => resizeLocalFromScene(identity.map(() => NaN), identity), /Invalid/);
    const skew = identity.slice(); skew[4] = .2;
    assert.throws(() => resizeLocalFromScene(skew, identity), /Invalid/);
});

function fixture({wrongPin = false, oversizedChildren = false} = {}) {
    const memory = Buffer.alloc(1 << 20), scene = new Map(), callbacks = new Map(), errors = [], frees = [];
    let next = 1024, writes = 0;
    class Pointer {
        constructor(address) { this.address = Number(address); }
        add(n) { return new Pointer(this.address + n); }
        sub(other) { return new Pointer(this.address - other.address); }
        equals(other) { return this.address === other.address; }
        toString() { return String(this.address); }
        toInt32() { return this.address | 0; }
        isNull() { return this.address === 0; }
        readU64() { return memory.readBigUInt64LE(this.address); }
        readU32() { return memory.readUInt32LE(this.address); }
        writeU32(v) { memory.writeUInt32LE(v, this.address); }
        readU8() { return memory.readUInt8(this.address); }
        writeU8(v) { memory.writeUInt8(v, this.address); }
        writeU64(v) { memory.writeBigUInt64LE(BigInt(v.toString()), this.address); }
        readPointer() { return new Pointer(this.readU64()); }
        writePointer(p) { this.writeU64(p.address); }
        readFloat() { return memory.readFloatLE(this.address); }
        writeFloat(v) { memory.writeFloatLE(v, this.address); }
        readUtf8String(n) { return memory.toString('utf8', this.address, this.address + n); }
    }
    const ptr = n => new Pointer(n);
    const alloc = size => { const p = ptr(next); next += size + 16; return p; };
    const parts = id => [BigInt(id), ptr(id * 16)];
    function nodeHandle(id) { const p = alloc(16); p.writeU64(id); p.add(8).writePointer(ptr(id * 16)); return p; }
    function node(id, name, parent, matrix = identity) {
        const data = alloc(64), text = alloc(name.length + 1);
        matrix.forEach((v, i) => data.add(i * 4).writeFloat(v));
        memory.write(name, text.address);
        scene.set(id, {id, name, parent, data, text, valid: true});
    }
    node(1, 'space-transform-task-42', 0);
    node(2, 'window-task-42', 1, turn);
    node(3, 'Highlight', 1, baseline);
    node(4, 'Resize Placeholder Visual', 1, baseline);
    const controller = alloc(0xa0);
    controller.add(0x20).writeU32(3);
    controller.add(0x98).writePointer(ptr(301));
    const freeform = alloc(0xe0);
    freeform.add(0x3c).writeFloat(.75); freeform.add(0x40).writeFloat(5);
    const at = p => scene.get(p.readU32());
    const pointAt = p => [0, 1, 2].map(i => p.add(i * 4).readFloat());
    const matrixAt = p => Array.from({length: 16}, (_, i) => at(p).data.add(i * 4).readFloat());
    const localPoint = (p, point) => {
        const m = matrixAt(p), world = pointAt(point);
        // The fixture owner has only a scale and translation, independently of the window rotation.
        return world.map((v, i) => (v - m[12 + i]) / m[i * 5]);
    };
    const symbols = new Map();
    const implementations = {
        '_ZNK3imp9Component7GetNodeEv': p => parts(p.equals(controller) || p.equals(freeform) ? 1 : p.address === 301 ? 3 : 4),
        '_ZNK3imp10NodeHandle7IsValidEv': p => Boolean(at(p)?.valid),
        '_ZNK3imp4Node9GetParentEv': p => [BigInt(at(p).parent) | (0xfff0n << 32n), ptr(at(p).parent * 16)],
        '_ZNK3imp4Node7GetNameEv': p => [at(p).text, at(p).name.length],
        '_ZNK3imp4Node11GetChildrenEv': p => {
            const nodes = [...scene.values()].filter(n => n.parent === at(p).id);
            const data = alloc(nodes.length * 16);
            nodes.forEach((n, i) => {
                data.add(i * 16).writeU64(n.id);
                data.add(i * 16 + 8).writePointer(ptr(n.id * 16));
            });
            return [data, data.add((oversizedChildren ? 65 : nodes.length) * 16), data.add(nodes.length * 16)];
        },
        '_ZNK3imp4Node11GetLocalTrsEv': p => at(p).data,
        '_ZN3imp4Node11SetLocalTrsERKN8filament4math7details6TMat44IfEE': (p, data) => {
            assert.ok(at(p).valid, 'must not write a released node');
            memory.copy(memory, at(p).data.address, data.address, data.address + 64); writes++;
        },
        '_ZNK3imp4Node19LocalFromWorldPointERKN8filament4math7details5TVec3IfEE': localPoint,
        '_ZNK3imp4Node19WorldFromLocalPointERKN8filament4math7details5TVec3IfEE': (p, point) => transformPoint(matrixAt(p), pointAt(point)),
        '_ZdlPv': p => frees.push(p.address),
    };
    const offsets = [0x12e24f8, 0x12f1964, 0x12ec70c, 0x12ebe2c, 0x12ec75c, 0x12ecc64, 0x12ec510, 0x12ed824, 0x12ee4bc];
    Object.keys(implementations).slice(0, 9).forEach((s, i) => symbols.set(s, offsets[i]));
    const renderStateSymbol = '_ZN2ix6moohan5sysui16ReformController21GetCurrentRenderStateERKNSt3__18optionalIN3imp13GenericRayHitIfEEEE';
    symbols.set(renderStateSymbol, 0x4d13470);
    const resizeSolverSymbol = '_ZN2ix6moohan5sysui13PanelResizing19ComputeNewPanelSizeERKN3imp10GenericRayIfEES7_NS3_10NodeHandleERKN8filament4math7details5TVec2IfEERKNS2_11ConstraintsENSt3__18optionalINSB_6TMat44IfEEEE';
    const moveSolverSymbol = '_ZN2ix6moohan5sysui19FreeformPositioning23ComputeUpdatedMoveStateERKN3imp10GenericRayIfEES7_RKNS2_9MoveStateE';
    symbols.set(resizeSolverSymbol, 0x4f2efb0);
    for (const [type, values] of [['15HighlightVisual', [0x4d0ba98, 0x4d0c194, 0x4c97c60, 0x4c97d30]],
        ['23ResizePlaceholderVisual', [0x4d1622c, 0x4d16074, 0x4c99828, 0x4c998f8]]]) {
        const names = [`_ZN2ix6moohan5sysui${type}6UpdateERKN3imp9FrameTimeE`,
            `_ZN2ix6moohan5sysui${type}21UpdateSizeAndPositionERKN8filament4math7details5TVec2IfEERKNS5_5TVec3IfEE`,
            `_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE12NotifyActiveEPNS_9ComponentEb`,
            `_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE7CleanupERNS_9ComponentE`];
        names.forEach((s, i) => symbols.set(s, values[i]));
    }
    globalThis.Memory = {alloc, copy: (a, b, size) => memory.copy(memory, a.address, b.address, b.address + size)};
    const exported = (s, base) => {
        const offset = s === moveSolverSymbol ? (base === 0x30000000 ? 0x4f2a4c0 : 0x4d096e8) : symbols.get(s);
        assert.notEqual(offset, undefined, s);
        const p = ptr(base + offset + (wrongPin ? 4 : 0));
        p.symbol = s === moveSolverSymbol ? s + ':' + base : s;
        return p;
    };
    globalThis.Process = {getModuleByName: n => {
        assert.ok(['libImpress-jni-vulkan.so', 'libsysui_jni_soong_vulkan.so', 'libspaceflinger_jni_vulkan.so'].includes(n), 'wrong renderer target: ' + n);
        const base = n.startsWith('libImpress') ? 0x20000000 : n.startsWith('libspaceflinger') ? 0x30000000 : 0x10000000;
        return {name: n, base: ptr(base), getExportByName: s => exported(s, base)};
    }};
    globalThis.Module = {getGlobalExportByName: s => { const p = ptr(1); p.symbol = s; return p; }};
    globalThis.NativeFunction = function (p) { assert.ok(implementations[p.symbol]); return implementations[p.symbol]; };
    globalThis.Interceptor = {attach: (p, callback) => {
        callbacks.set(p.symbol, callback);
        return {detach: () => callbacks.delete(p.symbol)};
    }};
    const allowed = new Set([42]);
    const distanceAllowed = new Set([42]);
    function invoke(fragment, component = 301, original = () => {}) {
        const symbol = [...callbacks.keys()].find(s => s.includes(fragment));
        assert.ok(symbol, fragment);
        const callback = callbacks.get(symbol), context = {};
        callback.onEnter?.call(context, [ptr(component), ptr(component), ptr(0)]);
        original();
        callback.onLeave?.call(context);
    }
    function hit(point, present = true) {
        const result = alloc(0x68);
        result.add(0x60).writeU8(present ? 1 : 0);
        point.forEach((v, i) => result.add(0x14 + i * 4).writeFloat(v));
        return result;
    }
    function classify(hit) {
        const flags = controller.add(0x20).readU32();
        if (hit.add(0x60).readU8() === 0 || flags === 0) return 0;
        if ((flags & 2) === 0) return 1;
        const point = localPoint(nodeHandle(1), hit.add(0x14));
        const position = pointAt(scene.get(3).data.add(12 * 4));
        const x = point[0] - position[0], y = point[1] - position[1];
        // AZJ2 GetCurrentRenderState: panel half-size minus corner width, then stock corner states.
        if (x < -.9 && y > 1.4) return 2;
        if (x < -.9 && y < -1.4) return 4;
        if (x > .9 && y > 1.4) return 3;
        if (x > .9 && y < -1.4) return 5;
        return flags & 1;
    }
    function renderState(hit) {
        const callback = callbacks.get(renderStateSymbol), context = {}, args = [controller, hit];
        callback.onEnter.call(context, args);
        const state = classify(args[1]);
        callback.onLeave.call(context, ptr(state));
        return {state, hit: args[1]};
    }
    function resizeFrame(frame, {caller = true, present = true, owner = 1, during = () => {}} = {}) {
        const data = alloc(0x50);
        frame.forEach((v, i) => data.add(i * 4).writeFloat(v));
        data.add(0x40).writeU8(present ? 1 : 0);
        const args = [ptr(0), ptr(0), ptr(0), ptr(owner), ptr(owner * 16), ptr(0), ptr(0), data];
        const context = {returnAddress: ptr(caller ? 0x30000000 + 0x4d25c58 : 0)};
        const callback = callbacks.get(resizeSolverSymbol);
        callback.onEnter.call(context, args);
        const result = {original: Array.from({length: 16}, (_, i) => data.add(i * 4).readFloat()),
            frame: Array.from({length: 16}, (_, i) => args[7].add(i * 4).readFloat()), copied: !args[7].equals(data)};
        during(); callback.onLeave.call(context);
        return result;
    }
    function beginMove({caller = true, ui = false} = {}) {
        const callback = callbacks.get(moveSolverSymbol + ':' + (ui ? 0x10000000 : 0x30000000));
        const context = {returnAddress: ptr(caller ? 0x30000000 + 0x4d25a08 : 0)};
        callback.onEnter.call(context, [freeform]);
        return () => callback.onLeave.call(context);
    }
    const read = id => Array.from({length: 16}, (_, i) => scene.get(id).data.add(i * 4).readFloat());
    return {scene, allowed, distanceAllowed, errors, frees, callbacks, invoke, read, node, nodeHandle, ptr, controller, hit,
        classify, renderState, resizeFrame, freeform, beginMove,
        bytes: p => Buffer.from(memory.subarray(p.address, p.address + 0x68)),
        start: () => installBoundaryAlignment(id => allowed.has(id), e => errors.push(e), id => distanceAllowed.has(id)),
        get writes() { return writes; }};
}

test('native visuals align once per frame, preserve stock resize, and wait for cleanup', () => {
    const f = fixture(), boundary = f.start();
    const update = '15HighlightVisual6Update', resize = '15HighlightVisual21UpdateSizeAndPosition';
    f.invoke(update, 301, () => f.invoke(resize));
    near(f.read(3), boundaryTransform(turn, baseline));
    let diagnostics = boundary.getDiagnostics();
    assert.equal(diagnostics.renderer, 'libsysui_jni_soong_vulkan.so');
    assert.equal(diagnostics.highlightUpdates, 1);
    assert.equal(diagnostics.resizes, 1);
    assert.equal(diagnostics.aligned, 1);
    assert.equal(diagnostics.last, 'aligned');
    assert.ok(diagnostics.path.includes('window-task-42'));
    diagnostics.parents.length = 0;
    assert.deepEqual(boundary.getDiagnostics().parents, ['space-transform-task-42']);
    f.invoke(update, 301, () => near(f.read(3), baseline));
    near(f.read(3), boundaryTransform(turn, baseline)); // No cumulative rotation.
    f.invoke('23ResizePlaceholderVisual6Update', 302);
    assert.equal(boundary.getDiagnostics().placeholderUpdates, 1);
    near(f.read(4), boundaryTransform(turn, baseline));
    const newSize = baseline.slice(); newSize[0] = 4;
    f.invoke(resize, 301, () => newSize.forEach((v, i) => f.scene.get(3).data.add(i * 4).writeFloat(v)));
    near(f.read(3), boundaryTransform(turn, newSize));
    assert.ok(f.frees.length > 0, 'returned child vectors must be freed');
    boundary.stop();
    assert.equal(boundary.isRestored(), false);
    assert.throws(() => boundary.dispose(), /pending/);
    f.invoke(update); near(f.read(3), newSize);
    assert.equal(boundary.isRestored(), false);
    f.invoke('23ResizePlaceholderVisualEE12NotifyActive', 302);
    near(f.read(4), baseline);
    assert.equal(boundary.isRestored(), true);
    boundary.dispose(); assert.equal(f.callbacks.size, 0); assert.deepEqual(f.errors, []);
});

test('stock corner selection sees a corrected copy, including a transformed owner', () => {
    for (const rotation of [turn, pitch, yaw, boundaryTransform(turn, boundaryTransform(pitch, yaw))]) {
        const f = fixture(), boundary = f.start();
        const owner = [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 1, 2, 3, 1];
        f.node(1, 'space-transform-task-42', 0, owner);
        f.node(2, 'window-task-42', 1, rotation);
        f.invoke('15HighlightVisual6Update');
        const aligned = boundaryTransform(rotation, baseline);
        for (const [i, corner] of corners.entries()) {
            const hit = f.hit(transformPoint(owner, transformPoint(aligned, corner)));
            const original = f.bytes(hit), corrected = f.renderState(hit);
            assert.equal(corrected.state, [2, 3, 4, 5][i]);
            assert.notEqual(corrected.hit.toString(), hit.toString());
            assert.deepEqual(f.bytes(hit), original, 'original ray hit is never mutated');
        }
        const center = f.hit(transformPoint(owner, transformPoint(aligned, [0, 0, 0])));
        assert.equal(f.renderState(center).state, 1, 'window body retains stock move classification');
        const diagnostics = boundary.getDiagnostics();
        assert.equal(diagnostics.resizeHitTests, 5);
        assert.equal(diagnostics.resizeCornerHits, 4);
        boundary.stop(); f.invoke('15HighlightVisual6Update'); boundary.dispose();
        assert.deepEqual(f.errors, []);
    }
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    const point = f.hit(transformPoint(boundaryTransform(turn, baseline), corners[0]));
    assert.notEqual(f.classify(point), 2, 'regression: rotated top-left fails the original flat-space test');
    assert.equal(f.renderState(point).state, 2);
    boundary.stop(); f.invoke('15HighlightVisual6Update'); boundary.dispose();
});

test('resize solver receives an owned corrected frame only for the pinned app path', () => {
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    const result = f.resizeFrame(identity);
    assert.ok(result.copied);
    near(result.original, identity);
    near(result.frame, resizeLocalFromScene(turn, identity));
    for (const options of [{caller: false}, {present: false}, {owner: 99}]) {
        assert.equal(f.resizeFrame(identity, options).copied, false);
    }
    f.allowed.clear(); assert.equal(f.resizeFrame(identity).copied, false);
    f.allowed.add(42);
    assert.equal(boundary.getDiagnostics().resizeFrames, 1);
    boundary.stop(); assert.equal(f.resizeFrame(identity).copied, false);
    f.invoke('15HighlightVisual6Update'); boundary.dispose();
    assert.deepEqual(f.errors, []);
});

test('10x movement limit is temporary, does not compound, and survives rotation being off', () => {
    const f = fixture(), boundary = f.start();
    f.allowed.clear(); // Distance follows live app bindings independently of rotation controls.
    for (const ui of [false, true, false]) {
        const finish = f.beginMove({ui});
        assert.equal(f.freeform.add(0x3c).readFloat(), .75);
        assert.equal(f.freeform.add(0x40).readFloat(), 50);
        finish(); assert.equal(f.freeform.add(0x40).readFloat(), 5);
    }
    const first = f.beginMove(), second = f.beginMove({ui: true});
    assert.equal(f.freeform.add(0x40).readFloat(), 50);
    first(); assert.equal(f.freeform.add(0x40).readFloat(), 50);
    boundary.stop(); assert.equal(boundary.isRestored(), false);
    second(); assert.equal(f.freeform.add(0x40).readFloat(), 5);
    assert.equal(boundary.isRestored(), true);
    const unmodified = f.beginMove(); assert.equal(f.freeform.add(0x40).readFloat(), 5); unmodified();
    assert.deepEqual(boundary.getDiagnostics().distanceLimit, {task: 42, stock: 5, maximum: 50});
    boundary.dispose(); assert.deepEqual(f.errors, []);
});

test('shutdown waits until the native solver releases its owned frame copy', () => {
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    f.resizeFrame(identity, {during() {
        boundary.stop(); f.invoke('15HighlightVisual6Update');
        assert.equal(boundary.isRestored(), false);
        assert.equal(boundary.getDiagnostics().inFlightInputs, 1);
    }});
    assert.equal(boundary.isRestored(), true);
    boundary.dispose(); assert.deepEqual(f.errors, []);
});

test('distance guards leave other callers, apps and invalid ranges alone', () => {
    const f = fixture(), boundary = f.start();
    const wrong = f.beginMove({caller: false}); assert.equal(f.freeform.add(0x40).readFloat(), 5); wrong();
    f.distanceAllowed.clear();
    const excluded = f.beginMove(); assert.equal(f.freeform.add(0x40).readFloat(), 5); excluded();
    f.distanceAllowed.add(42);
    for (const maximum of [0, .5, NaN, Infinity, 101]) {
        f.freeform.add(0x40).writeFloat(maximum);
        const finish = f.beginMove(); assert.ok(Object.is(f.freeform.add(0x40).readFloat(), maximum)); finish();
    }
    f.freeform.add(0x40).writeFloat(5);
    const reconfigured = f.beginMove();
    f.freeform.add(0x40).writeFloat(7); // A genuine stock update owns the new value.
    reconfigured(); assert.equal(f.freeform.add(0x40).readFloat(), 7);
    boundary.stop(); boundary.dispose(); assert.deepEqual(f.errors, []);
});

test('flat, unowned, disabled and stale visuals keep the original hit', () => {
    for (const condition of ['unowned', 'flat', 'no-hit', 'move-only', 'disabled', 'stopping', 'lost-node', 'reparented']) {
        const f = fixture(), boundary = f.start();
        if (condition === 'flat') f.node(2, 'window-task-42', 1);
        if (condition !== 'unowned') f.invoke('15HighlightVisual6Update');
        if (condition === 'move-only') f.controller.add(0x20).writeU32(1);
        if (condition === 'disabled') f.allowed.clear();
        if (condition === 'stopping') boundary.stop();
        if (condition === 'lost-node') f.scene.get(3).valid = false;
        if (condition === 'reparented') f.scene.get(3).parent = 2;
        const hit = f.hit([.1, .2, .3], condition !== 'no-hit');
        assert.equal(f.renderState(hit).hit.toString(), hit.toString(), condition);
        assert.equal(boundary.getDiagnostics().resizeHitTests, 0);
        boundary.stop(); f.invoke('15HighlightVisual6Update'); boundary.dispose();
        assert.deepEqual(f.errors, []);
    }
});

test('invalid pointer coordinates stop alignment without replacing the original hit', () => {
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    const hit = f.hit([NaN, 0, 0]);
    assert.equal(f.renderState(hit).hit.toString(), hit.toString());
    assert.equal(f.errors.length, 1);
    assert.match(String(f.errors[0]), /Invalid resize/);
    assert.equal(boundary.isRestored(), false);
    f.invoke('15HighlightVisual6Update'); boundary.dispose();
});

test('node loss, eligibility loss and hierarchy changes leave no stale writes', () => {
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    f.allowed.clear(); f.invoke('15HighlightVisual6Update'); near(f.read(3), baseline);
    f.allowed.add(42); f.invoke('15HighlightVisual6Update');
    f.scene.get(3).valid = false;
    const before = f.writes;
    f.invoke('15HighlightVisualEE7Cleanup'); assert.equal(f.writes, before);
    f.node(3, 'Highlight', 1, baseline);
    const leash = identity.slice(); leash[12] = .3;
    f.node(5, 'window-leash', 1, leash);
    f.scene.get(2).parent = 5;
    f.invoke('15HighlightVisual6Update'); // A bounded intermediate transform is supported.
    near(f.read(3), boundaryTransform(boundaryTransform(leash, turn), baseline));
    boundary.stop(); f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.isRestored(), true); boundary.dispose();
    assert.deepEqual(f.errors, []);
});

test('ABI pin mismatch installs no hooks', () => {
    const f = fixture({wrongPin: true});
    assert.throws(() => f.start(), /symbol mismatch/);
    assert.equal(f.callbacks.size, 0);
});

test('unrepresentable transitions are skipped and malformed child vectors are freed', () => {
    const f = fixture(), boundary = f.start();
    const nonuniform = turn.slice(); nonuniform[1] = 2;
    nonuniform.forEach((v, i) => f.scene.get(2).data.add(i * 4).writeFloat(v));
    f.invoke('15HighlightVisual6Update'); near(f.read(3), baseline);
    assert.equal(f.writes, 0);
    assert.equal(boundary.getDiagnostics().last, 'nonuniform-or-skewed');
    boundary.stop(); assert.equal(boundary.isRestored(), true); boundary.dispose();
    const bad = fixture({oversizedChildren: true}), failed = bad.start();
    bad.invoke('15HighlightVisual6Update');
    assert.equal(bad.errors.length, 1);
    assert.match(String(bad.errors[0]), /child count/);
    assert.equal(bad.frees.length, 1);
    assert.equal(bad.writes, 0);
    assert.equal(failed.isRestored(), true); failed.dispose();
});

test('diagnostics distinguish absent callbacks, unmatched parents, missing windows and eligibility', () => {
    const f = fixture(), boundary = f.start();
    assert.equal(boundary.getDiagnostics().last, 'waiting-for-callback');
    f.node(1, 'unmatched-parent', 0);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().rejected['parent-name'], 1);
    assert.ok(boundary.getDiagnostics().parents.includes('unmatched-parent'));
    f.node(1, 'space-transform-task-42', 0);
    f.allowed.clear(); f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'task-not-ready');
    f.allowed.add(42);
    f.node(2, 'other-window', 1);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'window-missing');
    assert.ok(boundary.getDiagnostics().path.includes('other-window'));
    f.node(2, 'window-task-42', 1);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'identity');
    assert.equal(f.writes, 0);
    boundary.stop(); boundary.dispose();
});
