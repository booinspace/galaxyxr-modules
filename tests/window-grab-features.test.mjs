import test from 'node:test';
import assert from 'node:assert/strict';
import {parseFeatureCommand, applyFeatureSettings} from '../scripts/curvature-features-agent.mjs';
import {readHandActionEvent, chooseGrabHand, installGrabRotation} from '../scripts/curvature-grab-agent.mjs';

test('settings protocol rejects extra tokens and gates grab with rotation', () => {
    for (const invalid of ['features 1 1 1 2', 'features 1 1 1 0;id', 'features 1 1', 'features true 1 1 0']) {
        assert.equal(parseFeatureCommand(invalid), null);
    }
    assert.deepEqual(parseFeatureCommand('features 0 1 0 1'), [false, true, false, true]);
    const calls = [], Features = {curvature: {value: true}};
    const session = {getValue: () => .5, set: v => calls.push(['curve', v])};
    const tasks = new Map([[42, {session, attachments: [{ticket: {close: () => calls.push(['menu'])}}]}]]);
    applyFeatureSettings([false, true, false, true], {
        Features, tasks,
        rotation: {setEnabled: v => calls.push(['rotation', v])},
        grab: {setEnabled: v => calls.push(['grab', v])},
        borderless: {setEnabled: v => calls.push(['borderless', v])},
    });
    assert.equal(Features.curvature.value, false);
    assert.deepEqual(calls, [['rotation', false], ['grab', false], ['borderless', true], ['curve', 0], ['menu']]);
});

function handFixture() {
    const memory = Buffer.alloc(8192), event = 128, buckets = 512;
    function pointer(at) {
        return {
            add: delta => pointer(at + delta), isNull: () => at === 0,
            address: at, readU8: () => memory.readUInt8(at), readS16: () => memory.readInt16LE(at),
            readU32: () => memory.readUInt32LE(at), readFloat: () => memory.readFloatLE(at),
            readU64: () => ({toNumber: () => Number(memory.readBigUInt64LE(at))}),
            readPointer: () => pointer(Number(memory.readBigUInt64LE(at))),
            readUtf8String: length => memory.toString('utf8', at, at + length),
        };
    }
    function text(at, value, heap = false) {
        if (heap) {
            memory.writeUInt8(1, at);
            memory.writeBigUInt64LE(BigInt(value.length), at + 8);
            memory.writeBigUInt64LE(4096n, at + 16);
            memory.write(value, 4096);
        } else {
            memory.writeUInt8(value.length * 2, at);
            memory.write(value, at + 1);
        }
    }
    text(event + 0x18, '/user/hand/left');
    memory.writeBigUInt64LE(BigInt(buckets), event + 0x50);
    memory.writeBigUInt64LE(4n, event + 0x58);
    for (let i = 0; i < 4; i++) memory.writeInt16LE(-1, buckets + i * 0x80 + 4);
    function action(slot, name, type) {
        const at = buckets + slot * 0x80;
        memory.writeInt16LE(0, at + 4);
        text(at + 8, name);
        memory.writeUInt32LE(type, at + 0x78);
        memory.writeUInt8(1, at + 0x20 + 0x28);
        return at + 0x20;
    }
    const grip = action(0, 'grip', 4), pinch = action(1, 'pinch_gesture', 1);
    memory.writeFloatLE(1, grip + 0x44);
    memory.writeFloatLE(.95, pinch + 0x2c);
    return {memory, event, buckets, grip, pinch, text, pointer: pointer(event)};
}

test('stock hand reader preserves full roll and supports both source paths without writing input', () => {
    const f = handFixture();
    f.memory.writeFloatLE(Math.SQRT1_2, f.grip + 0x44);
    f.memory.writeFloatLE(Math.SQRT1_2, f.grip + 0x40);
    f.memory.writeFloatLE(NaN, f.grip + 0x2c); // Translation is not used.
    const before = Buffer.from(f.memory);
    const data = readHandActionEvent(f.pointer, 500);
    assert.equal(data.hand, 0);
    assert.equal(data.reason, 'accepted');
    assert.equal(data.sample.pinching, true);
    assert.equal(data.sample.sampledAt, 500);
    assert.ok(Math.abs(data.sample.q[0] - Math.SQRT1_2) < 1e-6);
    assert.ok(Math.abs(data.sample.q[3] - Math.SQRT1_2) < 1e-6);
    assert.deepEqual(f.memory, before);
    f.text(f.event + 0x18, '/user/hand/right', true);
    assert.equal(readHandActionEvent(f.pointer, 500).hand, 1);
    f.text(f.event + 0x18, '/user/controller/left');
    assert.equal(readHandActionEvent(f.pointer, 500), null);
});

test('stock hand reader rejects inactive, malformed, non-finite and oversized input', () => {
    const f = handFixture();
    f.memory.writeUInt8(0, f.grip + 0x28);
    assert.equal(readHandActionEvent(f.pointer, 0).reason, 'inactive-grip');
    f.memory.writeUInt8(1, f.grip + 0x28);
    f.memory.writeFloatLE(NaN, f.grip + 0x44);
    assert.equal(readHandActionEvent(f.pointer, 0).reason, 'invalid-grip');
    f.memory.writeFloatLE(1, f.grip + 0x44);
    f.memory.writeFloatLE(2, f.pinch + 0x2c);
    assert.equal(readHandActionEvent(f.pointer, 0).reason, 'invalid-pinch');
    f.memory.writeUInt8(0, f.pinch + 0x28);
    assert.equal(readHandActionEvent(f.pointer, 0).sample.pinching, false);
    f.memory.writeUInt32LE(1, f.buckets + 0x78);
    assert.throws(() => readHandActionEvent(f.pointer, 0), /action type/);
    f.memory.writeUInt32LE(4, f.buckets + 0x78);
    f.memory.writeBigUInt64LE(257n, f.event + 0x58);
    assert.throws(() => readHandActionEvent(f.pointer, 0), /action table/);
});

test('native observation covers both stock consumers, preserves delivery and cancels after tracking loss', () => {
    const hand = handFixture(), handlers = new Map(), calls = [], logs = [];
    const addresses = [0x4dc9bf0, 0x4d89180];
    const pointer = address => ({
        address, add: delta => pointer(address + delta), equals: other => address === other.address,
        readU32: () => addresses.includes(address) ? 0xd503233f
            : address === addresses[0] + 4 ? 0x6db63bef : 0xa9bb7bfd,
    });
    const original = {implementation: null, call() { calls.push('stock'); return 123; }};
    const saved = {Process: globalThis.Process, Interceptor: globalThis.Interceptor, log: console.log};
    console.log = value => logs.push(value);
    globalThis.Process = {getModuleByName: () => ({base: pointer(0), getExportByName: name =>
        pointer(name.includes('10HandDevice') ? addresses[0] : addresses[1])})};
    globalThis.Interceptor = {attach(address, callbacks) {
        handlers.set(address.address, callbacks);
        return {detach: () => handlers.delete(address.address)};
    }};
    try {
        const controller = {setGrabEnabled: value => calls.push(['enabled', value]),
            cancelGrabs: () => calls.push('cancel'),
            onGrab: (...args) => calls.push(['grab', args[2]])};
        const Java = {perform: callback => callback(), array: (_type, values) => values,
            use: () => ({onEvent: {overload: () => original}})};
        let now = 1000;
        const grab = installGrabRotation(Java, controller, () => true, () => now);
        grab.setEnabled(true);
        function sample(backend = 0) { handlers.get(addresses[backend]).onEnter([null, hand.pointer]); }
        sample();
        grab.pulse(true);
        const owner = {getId: () => 42, reformOptions: {value: {flags: {value: 8}}}};
        const q = {w: {value: 1}, x: {value: 0}, y: {value: 0}, z: {value: 0}};
        function event(state) {
            return original.implementation.call({'this$0': {value: owner}},
                {type: {value: 1}, id: {value: 7}, state: {value: state}, proposedOrientation: {value: q}});
        }
        assert.equal(event(1), 123);
        now += 20; sample(1); event(2);
        hand.memory.writeUInt8(0, hand.grip + 0x28); sample(1);
        hand.memory.writeUInt8(1, hand.grip + 0x28);
        now += 20; sample(1); event(2);
        assert.deepEqual(calls.filter(call => Array.isArray(call) && call[0] === 'grab'),
            [['grab', 1], ['grab', 2], ['grab', 0]]);
        assert.equal(calls.filter(call => call === 'stock').length, 3);
        assert.ok(logs.includes('GXR_GRAB_STATE tracking'));
        now += 10001;
        grab.pulse(true);
        assert.equal(logs.at(-2), 'GXR_GRAB_STATE waiting', 'stale samples must not report tracking');
        const diagnostics = JSON.parse(logs.at(-1).slice('GXR_GRAB_DIAGNOSTICS '.length));
        assert.equal(diagnostics.source, 'stock-hand-input');
        assert.equal(diagnostics.legacyCalls, 1);
        assert.equal(diagnostics.axrifCalls, 3);
        assert.equal(diagnostics.acceptedSamples, 3);
        assert.equal(diagnostics.selectedGrabs, 1);
        assert.equal(diagnostics.q, undefined, 'diagnostics must not contain hand poses');
        hand.memory.writeUInt32LE(1, hand.buckets + 0x78);
        sample();
        assert.ok(logs.includes('GXR_GRAB_STATE unavailable'));
        assert.equal(original.implementation, null);
        assert.equal(handlers.size, 0, 'a reader error detaches both observers');
        grab.setEnabled(false);
    } finally {
        globalThis.Process = saved.Process;
        globalThis.Interceptor = saved.Interceptor;
        console.log = saved.log;
    }
});

test('grab selection refuses stale poses and ambiguous two-hand pinches', () => {
    const hand = {sampledAt: 1000, pinching: true};
    assert.equal(chooseGrabHand([hand, null], 1050), 0);
    assert.equal(chooseGrabHand([null, hand], 1050), 1);
    assert.equal(chooseGrabHand([hand, hand], 1050), null);
    assert.equal(chooseGrabHand([hand, null], 1101), null);
    assert.equal(chooseGrabHand([hand, null], 999), null);
    assert.equal(chooseGrabHand([{...hand, pinching: false}, null], 1050), null);
});
