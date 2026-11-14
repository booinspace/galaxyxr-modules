import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../modules/quick-settings-gesture/webroot/gesture.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function page(data = {enabled: 0, holdMs: 500}) {
    const commands = [], messages = [], elements = new Map();
    for (const id of ['quick-settings-gesture', 'quick-settings-enabled', 'quick-settings-hold',
        'quick-settings-options', 'quick-settings-save']) elements.set(id,
        {checked: false, value: '', disabled: true, events: {}, addEventListener(event, callback) { this.events[event] = callback; }});
    const context = {document: {getElementById: id => elements.get(id)},
        modulePath: '/data/adb/modules/gxr_window_curvature',
        exec: async command => { commands.push(command); return JSON.stringify(data); },
        message: (...args) => messages.push(args)};
    runInNewContext(source, context);
    return {elements, commands, messages, data};
}
test('native shortcut settings load and use only fixed root commands', async () => {
    const f = page();
    await flush();
    assert.equal(f.elements.get('quick-settings-enabled').checked, false);
    assert.equal(f.elements.get('quick-settings-hold').value, '500');
    assert.equal(f.elements.get('quick-settings-save').disabled, false);
    f.elements.get('quick-settings-enabled').checked = true;
    f.elements.get('quick-settings-hold').value = '0';
    await f.elements.get('quick-settings-gesture').events.submit({preventDefault() {}});
    assert.equal(f.commands.at(-1), 'sh /data/adb/modules/gxr_window_curvature/quick-settings-gesture.sh set 1 0');
    const count = f.commands.length;
    f.elements.get('quick-settings-hold').value = '0;id';
    await f.elements.get('quick-settings-gesture').events.submit({preventDefault() {}});
    assert.equal(f.commands.length, count);
    assert.match(f.messages.at(-1)[0], /supported/);
});
test('invalid saved values leave the shortcut form disabled', async () => {
    const f = page({enabled: 1, holdMs: 12});
    await flush();
    assert.equal(f.elements.get('quick-settings-save').disabled, true);
    assert.match(f.messages.at(-1)[0], /Invalid/);
});
