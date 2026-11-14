// Layouts come from the pinned AZJ2 HandDevice and AxrifInputManager consumers.
export function readHandActionEvent(event, sampledAt) {
    function text(at) {
        const heap = (at.readU8() & 1) !== 0;
        const length = heap ? at.add(8).readU64().toNumber() : at.readU8() >>> 1;
        if (!Number.isInteger(length) || length < 1 || length > 32) return '';
        const data = heap ? at.add(16).readPointer() : at.add(1);
        return data.isNull() ? '' : data.readUtf8String(length);
    }
    const hand = ['/user/hand/left', '/user/hand/right'].indexOf(text(event.add(0x18)));
    if (hand < 0) return null;
    const buckets = event.add(0x50).readPointer();
    const count = event.add(0x58).readU64().toNumber();
    if (buckets.isNull() || !Number.isInteger(count) || count < 1 || count > 256) {
        throw new Error('Invalid AZJ2 hand action table');
    }
    let grip = null, pinch = null;
    for (let i = 0; i < count; i++) {
        const slot = buckets.add(i * 0x80);
        if (slot.add(4).readS16() < 0) continue;
        const name = text(slot.add(8));
        if (name !== 'grip' && name !== 'pinch_gesture') continue;
        const type = slot.add(0x78).readU32();
        if (type !== (name === 'grip' ? 4 : 1)) throw new Error('Wrong AZJ2 hand action type');
        if (name === 'grip') grip = slot.add(0x20);
        else pinch = slot.add(0x20);
    }
    const inactive = reason => ({hand, sample: null, reason});
    if (grip === null || grip.add(0x28).readU8() !== 1) {
        return inactive('inactive-grip');
    }
    const q = [0x44, 0x38, 0x3c, 0x40].map(offset => grip.add(offset).readFloat());
    const norm = q.reduce((sum, value) => sum + value * value, 0);
    if (!q.every(Number.isFinite) || norm < .8 || norm > 1.2) return inactive('invalid-grip');
    let strength = 0;
    const pinchActive = pinch !== null && pinch.add(0x28).readU8() === 1;
    if (pinchActive) {
        strength = pinch.add(0x2c).readFloat();
        if (!Number.isFinite(strength) || strength < 0 || strength > 1) return inactive('invalid-pinch');
    }
    return {hand, reason: 'accepted', sample: {
        q: q.map(value => value / Math.sqrt(norm)), pinching: strength >= .8,
        pinchActive, pinchStrength: strength, sampledAt,
    }};
}

const handReaders = new Set();
let handHooks = [];

export function observeHandActions(onSample, onError, nowMs) {
    const reader = {onSample, onError, nowMs};
    function stop() {
        handReaders.delete(reader);
        if (handReaders.size === 0) {
            for (const hook of handHooks) hook.detach();
            handHooks = [];
        }
    }
    if (handReaders.size !== 0) {
        handReaders.add(reader);
        return {stop};
    }
    const lib = Process.getModuleByName('libspaceflinger_jni_vulkan.so');
    const sources = [
        ['legacyCalls', '_ZN12spaceflinger10HandDevice11updateStateERKN3imp16InputActionEventE',
            0x4dc9bf0, 0x6db63bef],
        ['axrifCalls', '_ZNK12spaceflinger17AxrifInputManager24populateHandsSourceStateERKN3imp16InputActionEventER22Axrif_HandsSourceState',
            0x4d89180, 0xa9bb7bfd],
    ].map(([name, symbol, offset, next]) => {
        const address = lib.getExportByName(symbol);
        if (!address.equals(lib.base.add(offset)) || address.readU32() !== 0xd503233f ||
            address.add(4).readU32() !== next) throw new Error('AZJ2 hand input symbol/code mismatch');
        return {name, address};
    });
    handReaders.add(reader);
    try {
        for (const source of sources) {
            handHooks.push(Interceptor.attach(source.address, {
                onEnter(args) {
                    for (const current of [...handReaders]) {
                        if (!handReaders.has(current)) continue;
                        try { current.onSample(readHandActionEvent(args[1], current.nowMs()), source.name); }
                        catch (error) {
                            handReaders.delete(current);
                            if (handReaders.size === 0) {
                                for (const hook of handHooks) hook.detach();
                                handHooks = [];
                            }
                            current.onError(error);
                        }
                    }
                },
            }));
        }
    } catch (error) { stop(); throw error; }
    return {stop};
}

export function chooseGrabHand(hands, now) {
    // A unique pinching hand is required; ambiguous two-hand grabs keep stock behavior.
    const candidates = hands.map((hand, index) => ({hand, index})).filter(({hand}) =>
        hand !== null && now >= hand.sampledAt && now - hand.sampledAt <= 100 && hand.pinching);
    return candidates.length === 1 ? candidates[0].index : null;
}

export function installGrabRotation(Java, controller, permitted, nowMs) {
    let enabled = false, callback = null;
    let input = null;
    let hands = [null, null], state = 'off', counters = null, lastDiagnostic = 0;
    const gestures = new Map();
    function log(value) {
        if (state === value) return;
        state = value;
        console.log('GXR_GRAB_STATE ' + value);
    }
    function quaternion(value) {
        if (value === null) return null;
        const q = [value.w.value, value.x.value, value.y.value, value.z.value];
        const norm = q.reduce((sum, component) => sum + component * component, 0);
        return q.every(Number.isFinite) && norm >= .8 && norm <= 1.2 ? q : null;
    }
    function stop() {
        enabled = false;
        if (input !== null) input.stop();
        input = null;
        const previousCallback = callback;
        callback = null;
        Java.perform(() => {
            if (previousCallback !== null) previousCallback.implementation = null;
            controller.setGrabEnabled(false);
        });
        gestures.clear();
        hands = [null, null];
    }
    function unavailable(error) {
        stop();
        log('unavailable');
        console.log('GXR_GRAB_ERROR ' + String(error.stack || error));
    }
    return {
        setEnabled(value) {
            if (value === enabled) return;
            if (!value) { stop(); log('off'); return; }
            try {
                enabled = true;
                counters = {source: 'stock-hand-input', legacyCalls: 0, axrifCalls: 0,
                    handCalls: 0, acceptedSamples: 0, moveStarts: 0, selectedGrabs: 0,
                    deliveredGrabs: 0, lastSample: 'none'};
                lastDiagnostic = nowMs();
                controller.setGrabEnabled(true);
                input = observeHandActions((data, source) => {
                    if (!enabled) return;
                    counters[source]++;
                    if (data === null) return;
                    counters.handCalls++;
                    counters.lastSample = data.reason;
                    hands[data.hand] = data.sample;
                    if (data.sample !== null) counters.acceptedSamples++;
                    else for (const gesture of gestures.values()) {
                        if (gesture.hand === data.hand) gesture.invalid = true;
                    }
                }, unavailable, nowMs);
                const type = Java.use('com.android.systemui.xr.spatial.SpaceFlingerTransformNode$reformEventCallback$1');
                callback = type.onEvent.overload('android.graphics.CPM$ReformEvent');
                const original = callback;
                callback.implementation = function (event) {
                    const result = original.call(this, event);
                    if (!enabled || !permitted() || event.type.value !== 1) return result;
                    try {
                        const owner = this['this$0'].value;
                        // Parent-relative reform proposals use a different basis.
                        if ((owner.reformOptions.value.flags.value & 4) !== 0) return result;
                        const id = event.id.value, state = event.state.value;
                        if (![1, 2, 3].includes(state) || id < 0) return result;
                        const key = String(owner.getId()) + ':' + id;
                        const now = nowMs();
                        if (state === 1) {
                            counters.moveStarts++;
                            const hand = chooseGrabHand(hands, now);
                            if (hand !== null && gestures.size < 16) {
                                counters.selectedGrabs++;
                                gestures.set(key, {hand, last: -Infinity, started: false});
                            }
                        }
                        const gesture = gestures.get(key);
                        if (gesture === undefined) return result;
                        const hand = hands[gesture.hand];
                        const valid = !gesture.invalid && hand !== null && now >= hand.sampledAt && now - hand.sampledAt <= 100;
                        const parent = quaternion(event.proposedOrientation.value);
                        if (!gesture.started) {
                            if (!valid || state === 3) { gestures.delete(key); return result; }
                            // Some start events have no proposed pose; wait for the first valid move.
                            if (parent === null) return result;
                        }
                        const phase = valid && parent !== null ? (gesture.started ? state : 1) : 0;
                        if (phase === 2 && now - gesture.last < 16) return result;
                        if (phase === 1) gesture.started = true;
                        gesture.last = now;
                        counters.deliveredGrabs++;
                        controller.onGrab(owner, id, phase,
                            Java.array('float', valid ? hand.q : [1, 0, 0, 0]),
                            Java.array('float', parent === null ? [1, 0, 0, 0] : parent), Math.floor(now));
                        if (phase === 0 || state === 3) gestures.delete(key);
                    } catch (error) { unavailable(error); }
                    return result;
                };
                log('waiting');
            } catch (error) { unavailable(error); }
        },
        pulse(home) {
            if (enabled) {
                const now = nowMs();
                const fresh = home && hands.some(hand => hand !== null &&
                    now >= hand.sampledAt && now - hand.sampledAt <= 100);
                log(fresh ? 'tracking' : 'waiting');
                if (now - lastDiagnostic >= 10000) {
                    console.log('GXR_GRAB_DIAGNOSTICS ' + JSON.stringify(counters));
                    lastDiagnostic = now;
                }
            }
            if (!home && gestures.size > 0) {
                gestures.clear();
                controller.cancelGrabs();
            }
        },
        stop,
    };
}
