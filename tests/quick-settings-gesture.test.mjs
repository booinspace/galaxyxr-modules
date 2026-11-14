import assert from 'node:assert/strict';
import test from 'node:test';
import {observeHandActions} from '../scripts/curvature-grab-agent.mjs';
import {PinchToggle, parseQuickSettingsCommand, installQuickSettingsGesture} from '../scripts/curvature-quick-settings-agent.mjs';

function sample(strength, now, hand = 0) {
    return {hand, sample: {pinchActive: true, pinchStrength: strength, sampledAt: now}};
}
function feed(policy, strength, from, to, hand = 0) {
    let count = 0;
    for (let now = from; now <= to; now += 50) count += policy.update(sample(strength, now, hand), now) ? 1 : 0;
    return count;
}

test('one half-second hold toggles once, requires full tracked release and works again', () => {
    const policy = new PinchToggle();
    assert.equal(feed(policy, 0, 0, 100), 0);
    assert.equal(feed(policy, 1, 150, 600), 0);
    assert.equal(policy.update(sample(1, 650), 650), true);
    assert.equal(feed(policy, 1, 700, 2000), 0, 'holding must not repeat');
    feed(policy, 0, 2050, 2150);
    assert.equal(feed(policy, 1, 2200, 2700), 1, 'same gesture can close the native panel');
});

test('right-hand input and tracking reacquisition cannot trigger a left shortcut', () => {
    const policy = new PinchToggle();
    feed(policy, 0, 0, 100);
    assert.equal(feed(policy, 1, 150, 800, 1), 0);
    assert.equal(feed(policy, 1, 850, 1500), 0, 'fresh release required after a long tracking gap');
    feed(policy, 0, 1550, 1650);
    feed(policy, 1, 1700, 1900);
    policy.update({hand: 0, sample: null}, 1950);
    assert.equal(feed(policy, 1, 2000, 2600), 0, 'loss during a pinch cancels it');
});

test('immediate mode still requires release, cooldown and valid timing', () => {
    const policy = new PinchToggle(0);
    assert.equal(feed(policy, 1, 0, 500), 0, 'never fire on a pinch already held at activation');
    feed(policy, 0, 550, 650);
    assert.equal(policy.update(sample(1, 700), 700), true);
    assert.equal(policy.update(sample(1, 700), 700), false, 'duplicate native consumers do not repeat');
    feed(policy, 0, 750, 850);
    assert.equal(feed(policy, 1, 900, 1400), 0, 'debounce rapid repeats');
    assert.equal(policy.update(sample(1, 1450), 1450), true);
    policy.reset();
    for (const invalid of [NaN, -1, 2]) assert.equal(policy.update(sample(invalid, 1500), 1500), false);
    assert.equal(policy.update(sample(0, 1700), 1600), false, 'future sample is invalid');
    assert.equal(policy.update(sample(0, 1400), 1600), false, 'stale sample is invalid');
    assert.equal(policy.update({hand: 0, sample: {...sample(0, 1600).sample, pinchActive: false}}, 1600), false);
    assert.throws(() => new PinchToggle(5), /Unsupported/);
});

test('root command protocol accepts only booleans and the two supported durations', () => {
    assert.deepEqual(parseQuickSettingsCommand('quick-settings 1 500'), {enabled: true, holdMs: 500});
    assert.deepEqual(parseQuickSettingsCommand('quick-settings 0 0'), {enabled: false, holdMs: 0});
    for (const value of ['quick-settings 2 500', 'quick-settings 1 100', 'quick-settings 1 0;id',
        'quick-settings true 500', 'quick-settings 1 500 extra']) assert.equal(parseQuickSettingsCommand(value), null);
});

test('shortcut observes independently of wrist grabbing and cleans up native readers', () => {
    const memory = Buffer.alloc(2048), event = 128, buckets = 512;
    const addresses = [0x4dc9bf0, 0x4d89180], handlers = new Map();
    function pointer(at) {
        return {add: n => pointer(at + n), isNull: () => at === 0, equals: p => at === p.at, at,
            readU8: () => memory.readUInt8(at), readS16: () => memory.readInt16LE(at),
            readU32: () => handlers.has(at) ? 0x14000000 : addresses.includes(at) ? 0xd503233f : at === addresses[0] + 4 ? 0x6db63bef
                : at === addresses[1] + 4 ? 0xa9bb7bfd : memory.readUInt32LE(at),
            readFloat: () => memory.readFloatLE(at),
            readU64: () => ({toNumber: () => Number(memory.readBigUInt64LE(at))}),
            readPointer: () => pointer(Number(memory.readBigUInt64LE(at))),
            readUtf8String: n => memory.toString('utf8', at, at + n)};
    }
    function text(at, value) { memory.writeUInt8(value.length * 2, at); memory.write(value, at + 1); }
    text(event + 0x18, '/user/hand/left');
    memory.writeBigUInt64LE(BigInt(buckets), event + 0x50);
    memory.writeBigUInt64LE(2n, event + 0x58);
    for (const [slot, name, type] of [[0, 'grip', 4], [1, 'pinch_gesture', 1]]) {
        const at = buckets + slot * 0x80;
        text(at + 8, name);
        memory.writeUInt32LE(type, at + 0x78);
        memory.writeUInt8(1, at + 0x48);
    }
    memory.writeFloatLE(1, buckets + 0x64);
    let now = 0, permitted = true, requests = 0, cancels = 0, searches = 0, closed = false;
    const logs = [], action = {}, context = {};
    const controller = {setEnabled() {}, cancel() { cancels++; }, request() { requests++; },
        close() { closed = true; }, $dispose() {}, getRequests: () => requests, getError: () => ''};
    const Java = {retain: value => value,
        use: () => ({currentApplication: () => ({getApplicationContext: () => context})}),
        choose(_type, callbacks) { searches++; callbacks.onMatch({getToggleQuickSettingsAction: () => action, $dispose() {}}); callbacks.onComplete(); }};
    const factory = {use: () => ({$new(c, a) { assert.equal(c, context); assert.equal(a, action); return controller; }})};
    const saved = {Process: globalThis.Process, Interceptor: globalThis.Interceptor};
    globalThis.Process = {getModuleByName: () => ({base: pointer(0), getExportByName: name => pointer(name.includes('10HandDevice') ? addresses[0] : addresses[1])})};
    globalThis.Interceptor = {attach(address, callback) { handlers.set(address.at, callback); return {detach: () => handlers.delete(address.at)}; }};
    try {
        const shortcut = installQuickSettingsGesture(Java, factory, () => permitted, () => now, (...args) => logs.push(args));
        assert.equal(searches, 0, 'disabled shortcut must not scan the heap or attach readers');
        let sharedSamples = 0;
        const wristReader = observeHandActions(() => sharedSamples++, assert.fail, () => now);
        shortcut.configure(true, 500);
        assert.equal(handlers.size, 2, 'wrist and shortcut share the verified hooks');
        function emit(strength, end) {
            memory.writeFloatLE(strength, buckets + 0x80 + 0x4c);
            for (; now <= end; now += 50) handlers.get(addresses[0]).onEnter([null, pointer(event)]);
        }
        emit(0, 100); emit(1, 650);
        assert.equal(requests, 1);
        permitted = false;
        emit(1, 1000);
        assert.ok(cancels > 0);
        assert.equal(requests, 1, 'expired supervisor cannot request a native action');
        shortcut.configure(false, 500);
        assert.equal(handlers.size, 2, 'disabling shortcut keeps wrist tracking attached');
        assert.ok(sharedSamples > 0);
        wristReader.stop();
        assert.equal(handlers.size, 0);
        shortcut.configure(true, 500);
        assert.equal(handlers.size, 2, 'a later enable validates the restored instructions');
        shortcut.stop();
        assert.equal(handlers.size, 0);
        assert.equal(closed, true);
        assert.ok(logs.some(([event]) => event === 'QUICK_SETTINGS_READY'));
    } finally { globalThis.Process = saved.Process; globalThis.Interceptor = saved.Interceptor; }
});
