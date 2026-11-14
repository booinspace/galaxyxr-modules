import assert from 'node:assert/strict';
import test from 'node:test';
import {installAudioMixer} from '../scripts/curvature-audio-agent.mjs';

function fixture({unavailable = false, attachFails = false} = {}) {
    let started = 0, stopped = 0, originalCalls = 0;
    const attached = [], logs = [];
    const popup = {implementation: null, call(...args) { originalCalls++; return 7; }};
    const expanded = {implementation: null, call(...args) { originalCalls++; return 9; }};
    const mixer = {
        start() { started++; }, stop() { stopped++; }, isStopped: () => stopped > 0,
        status: () => 'enabled=true owned=0',
        attach(...args) { if (attachFails) throw new Error('layout unavailable'); attached.push(args); },
    };
    const Java = {retain: value => value, use(name) {
        if (unavailable) throw new Error('unsupported firmware');
        if (name === 'android.app.ActivityThread') return {currentApplication: () => ({getApplicationContext: () => ({})})};
        if (name === 'com.android.systemui.volume.VolumeDialogImpl') return {showH: {overload: () => popup}};
        if (name === 'com.android.systemui.volume.VolumePanelDialog') return {onCreate: {overload: () => expanded}};
        throw new Error(name);
    }};
    const factory = {use: () => ({$new: () => mixer})};
    const controller = installAudioMixer(Java, factory, (...args) => logs.push(args));
    return {controller, popup, expanded, attached, logs,
        started: () => started, stopped: () => stopped, originalCalls: () => originalCalls};
}

test('extends both native panels after preserving their original methods', () => {
    const f = fixture();
    const dialog = {};
    const owner = {mDialog: {value: dialog}};
    assert.equal(f.popup.implementation.call(owner, 1, false, 0), 7);
    assert.equal(f.expanded.implementation.call(dialog, null), 9);
    assert.deepEqual(f.attached, [[dialog, false, owner], [dialog, true, null]]);
    assert.equal(f.originalCalls(), 2);
    assert.equal(f.started(), 1);
    f.controller.stop();
    assert.equal(f.popup.implementation, null);
    assert.equal(f.expanded.implementation, null);
    assert.equal(f.stopped(), 1);
    assert.ok(f.controller.isStopped());
});

test('unsupported APIs leave stock UI and Window Controls running', () => {
    const f = fixture({unavailable: true});
    assert.equal(f.started(), 0);
    assert.equal(f.popup.implementation, null);
    assert.equal(f.controller.status(), 'unavailable');
    assert.ok(f.logs.some(([event]) => event === 'AUDIO_MIXER_UNAVAILABLE'));
});

test('a mixer layout error cannot prevent the stock popup opening', () => {
    const f = fixture({attachFails: true});
    assert.equal(f.popup.implementation.call({mDialog: {value: {}}}, 1, false, 0), 7);
    assert.ok(f.logs.some(([event]) => event === 'AUDIO_MIXER_UI_ERROR'));
});
