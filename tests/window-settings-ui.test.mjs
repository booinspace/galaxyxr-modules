import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../modules/window-controls/webroot/settings.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function page(withRoot = true) {
    const elements = new Map(), commands = [], intervals = [];
    for (const name of ['status', 'runtime', 'features', 'switches', 'save', 'start', 'logs',
                        'curvature', 'borderless', 'rotation', 'grab']) {
        elements.set(name, {checked: false, disabled: false, textContent: '', events: {},
            classList: {toggle() {}}, addEventListener(type, listener) { this.events[type] = listener; }});
    }
    const data = {curvature: 1, borderless: 1, rotation: 1, grab: 0,
        runtime: 'RUNNING', grabRuntime: 'off', captionReady: 0};
    const context = {document: {getElementById: id => elements.get(id)},
        setTimeout: () => 1, clearTimeout() {}, setInterval: cb => intervals.push(cb)};
    context.window = context;
    if (withRoot) context.ksu = {exec(command, options, callback) {
        commands.push({command, options});
        context[callback](0, JSON.stringify(data), '');
    }};
    runInNewContext(source, context);
    return {elements, commands, intervals, data};
}

test('settings UI sends fixed boolean commands and status refresh preserves pending edits', async () => {
    const f = page();
    await flush();
    assert.equal(f.elements.get('curvature').checked, true);
    assert.equal(f.elements.get('grab').checked, false);
    assert.match(f.elements.get('runtime').textContent, /waiting up to 45 seconds/);
    f.data.captionReady = 1;
    await f.intervals[0]();
    assert.match(f.elements.get('runtime').textContent, /App window setup: ready/);
    f.elements.get('curvature').checked = false;
    f.elements.get('grab').checked = true;
    f.elements.get('features').events.submit({preventDefault() {}});
    await flush();
    assert.deepEqual(f.commands.at(-1),
        {command: 'sh /data/adb/modules/gxr_window_curvature/features.sh set 0 1 1 1', options: '{}'});
    f.elements.get('borderless').checked = false;
    f.data.grabRuntime = 'unavailable';
    await f.intervals[0]();
    assert.equal(f.elements.get('borderless').checked, false);
    assert.match(f.elements.get('runtime').textContent, /unavailable/);
    f.data.runtime = 'STARTING';
    f.data.grabRuntime = 'off';
    await f.intervals[0]();
    assert.match(f.elements.get('runtime').textContent, /90-second startup guard/);
    f.data.runtime = 'RUNNING';
    f.data.grabRuntime = 'waiting';
    await f.intervals[0]();
    assert.match(f.elements.get('runtime').textContent, /No fresh tracked hand pose/);
    assert.ok(f.commands.every(item => item.command.startsWith('sh /data/adb/modules/gxr_window_curvature/')));
});

test('a normal browser reports the missing KernelSU bridge', async () => {
    const f = page(false);
    await flush();
    assert.match(f.elements.get('status').textContent, /KernelSU GXR/);
    assert.equal(f.commands.length, 0);
});
