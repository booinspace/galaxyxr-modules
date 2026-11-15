import test from 'node:test';
import assert from 'node:assert/strict';
import {installPassthroughBlend} from '../scripts/curvature-passthrough-blend-agent.mjs';

function fixture(found = true) {
    const calls = [], content = {}, stock = {}, mixed = {};
    let permitted = true, stopped = false, error = '';
    const method = result => ({implementation: null, call() { calls.push('stock'); return result; }});
    const compute = method(stock), resume = method(stock), destroy = method(stock);
    const xr = {getContentView: () => content};
    const element = {getView: () => xr};
    const nativeManager = {$dispose() { calls.push('dispose-manager-wrapper'); }};
    const controller = {
        states(stack, value) { assert.equal(value, stock); calls.push('mix'); return mixed; },
        attach(root, owner) { assert.equal(root, content); assert.equal(owner, xr); calls.push('attach'); },
        detach(root) { assert.equal(root, content); calls.push('detach'); },
        close() { stopped = true; calls.push('close'); },
        isStopped: () => stopped, pulse: () => calls.push('pulse'),
        getError: () => error, getPercent: () => 50, getPanelHeightPx: () => 944, getLayout: () => 'row=500..580, media=594..800',
    };
    const Java = {
        retain: value => value,
        use(name) {
            if (name.endsWith('MixedRealityStateManager')) return {computeStates: compute};
            if (name.endsWith('QuickSettingsXrElement')) return {onResume: {overload: () => resume}, onDestroy: {overload: () => destroy}};
            if (name.endsWith('ActivityThread')) return {currentApplication: () => ({getApplicationContext: () => ({})})};
            throw new Error('Unexpected class ' + name);
        },
        choose(name, callbacks) {
            if (name.endsWith('PassthroughDimmerManager')) { if (found) callbacks.onMatch(nativeManager); }
            else if (name.endsWith('QuickSettingsXrElement')) callbacks.onMatch(element);
            else throw new Error('Unexpected search ' + name);
            callbacks.onComplete();
        },
    };
    const agent = installPassthroughBlend(Java, {use: () => ({$new: () => controller})},
        () => permitted, (...value) => calls.push(value));
    return {calls, stock, mixed, agent, compute, resume, destroy, content, element,
        permit(value) { permitted = value; }, fail(value) { error = value; }};
}

test('native roots use their content view, stock methods run once and the lease scopes mixed states', () => {
    const f = fixture();
    assert.ok(f.calls.includes('attach'));
    assert.equal(f.agent.status().layout, 'row=500..580, media=594..800');
    assert.equal(f.compute.implementation.call({}, {}, {}, {}, {}), f.mixed);
    f.permit(false);
    assert.equal(f.compute.implementation.call({}, {}, {}, {}, {}), f.stock);
    assert.equal(f.calls.filter(value => value === 'mix').length, 1);
    assert.equal(f.resume.implementation.call(f.element), f.stock);
    assert.equal(f.destroy.implementation.call(f.element), f.stock);
    assert.ok(f.calls.indexOf('detach') < f.calls.lastIndexOf('stock'));
    f.agent.stop();
    assert.equal(f.compute.implementation, null);
    assert.equal(f.resume.implementation, null);
    assert.equal(f.destroy.implementation, null);
    assert.ok(f.agent.isStopped());
});

test('an unavailable manager or Java-side error removes this feature without throwing into SystemUI', () => {
    const absent = fixture(false);
    assert.ok(absent.agent.isStopped());
    assert.ok(absent.calls.some(value => Array.isArray(value) && value[0] === 'PASSTHROUGH_BLEND_UNAVAILABLE'));
    const f = fixture();
    f.fail('test cleanup');f.agent.pulse();
    assert.equal(f.compute.implementation, null);
    assert.ok(f.agent.isStopped());
    assert.ok(f.calls.includes('close'));
});
