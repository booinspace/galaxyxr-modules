import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../modules/mic-gain-boost/webroot/settings.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function page(withRoot = true) {
    const elements = new Map(), commands = [];
    for (const id of ['status', 'controls', 'apply', 'start', 'logs', 'gain', 'gain-value', 'vd-only', 'settings']) {
        elements.set(id, {value: '', checked: false, disabled: false, textContent: '', events: {},
            classList: {toggle() {}}, addEventListener(type, listener) { this.events[type] = listener; }});
    }
    const context = {document: {getElementById: id => elements.get(id)}, setTimeout: () => 1, clearTimeout() {}};
    context.window = context;
    if (withRoot) context.ksu = {exec(command, options, callback) {
        commands.push(command);
        context[callback](0, JSON.stringify({gain: 15, vdOnly: 1, running: true}), '');
    }};
    runInNewContext(source, context);
    return {elements, commands};
}

test('gain UI submits bounded numeric values and scope; log export does not start the runtime', async () => {
    const p = page();
    await flush();
    assert.equal(p.elements.get('gain').value, '15');
    assert.equal(p.elements.get('vd-only').checked, true);
    p.elements.get('gain').value = '22';
    p.elements.get('gain').events.input();
    assert.equal(p.elements.get('gain-value').textContent, '+22 steps');
    p.elements.get('vd-only').checked = false;
    p.elements.get('settings').events.submit({preventDefault() {}});
    await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/settings.sh set 22 0');
    const count = p.commands.length;
    p.elements.get('gain').value = '15;id';
    p.elements.get('settings').events.submit({preventDefault() {}});
    await flush();
    assert.equal(p.commands.length, count);
    assert.match(p.elements.get('status').textContent, /Gain must be/);
    p.elements.get('logs').events.click();
    await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/control.sh export');
});

test('normal browsers explain that the KernelSU bridge is required', async () => {
    const p = page(false);
    await flush();
    assert.match(p.elements.get('status').textContent, /KernelSU GXR/);
    assert.equal(p.commands.length, 0);
});
