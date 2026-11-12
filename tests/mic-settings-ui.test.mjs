import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../modules/mic-gain-boost/webroot/settings.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function page(withRoot = true) {
    const elements = new Map(), commands = [];
    const state = {gain: 15, vdOnly: 1, running: true, recording: false};
    for (const id of ['status', 'controls', 'apply', 'start', 'logs', 'gain', 'gain-value', 'vd-only', 'settings',
        'record', 'delete-recording', 'play-recording', 'stop-playback', 'test-status']) {
        elements.set(id, {value: '', checked: false, disabled: false, textContent: '', events: {},
            classList: {toggle() {}}, addEventListener(type, listener) { this.events[type] = listener; }});
    }
    const context = {document: {getElementById: id => elements.get(id)}, setTimeout: () => 1, clearTimeout() {}};
    context.window = context;
    if (withRoot) context.ksu = {exec(command, options, callback) {
        commands.push(command);
        const settings = command.match(/settings\.sh set (\d+) ([01])$/);
        if (settings) { state.gain = Number(settings[1]); state.vdOnly = Number(settings[2]); }
        assert.ok(!/settings\.sh (record|play)$/.test(command), 'Audio must use the async bridge');
        if (command.endsWith('/settings.sh delete-recording')) state.recording = false;
        if (command.endsWith('/settings.sh stop-playback')) state.finishPlayback();
        context[callback](0, JSON.stringify(state), '');
    }, spawn(command, args, options, callback) {
        const parts = JSON.parse(args), verb = parts[1];
        assert.equal(command, 'sh');
        assert.equal(parts[0], '/data/adb/modules/gxr_mic_gain_azj2/settings.sh');
        assert.ok(['record', 'play'].includes(verb));
        commands.push(command + ' ' + parts.join(' '));
        const complete = () => {
            if ((verb === 'record' && state.failRecording) || (verb === 'play' && state.failPlayback)) {
                context[callback].stderr.emit('data', verb === 'record' ? 'Recording failed (exit 124).' : 'Native player error.');
                context[callback].emit('exit', 1);
            } else {
                if (verb === 'record') state.recording = true;
                context[callback].stdout.emit('data', verb === 'record' ? JSON.stringify(state) : '');
                context[callback].emit('exit', 0);
            }
        };
        if (verb === 'record' && state.deferRecording) state.finishRecording = complete;
        else if (verb === 'play' && state.deferPlayback) state.finishPlayback = complete;
        else complete();
    }};
    runInNewContext(source, context);
    return {elements, commands, state};
}

test('gain UI submits bounded numeric settings; export does not start the runtime', async () => {
    const p = page(); await flush();
    assert.equal(p.elements.get('gain').value, '15');
    p.elements.get('gain').value = '22'; p.elements.get('gain').events.input();
    assert.equal(p.elements.get('gain-value').textContent, '+22 steps');
    p.elements.get('vd-only').checked = false;
    p.elements.get('settings').events.submit({preventDefault() {}}); await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/settings.sh set 22 0');
    const count = p.commands.length;
    p.elements.get('gain').value = '15;id';
    p.elements.get('settings').events.submit({preventDefault() {}}); await flush();
    assert.equal(p.commands.length, count);
    p.elements.get('logs').events.click(); await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/control.sh export');
});

test('normal browsers explain that KernelSU is required', async () => {
    const p = page(false); await flush();
    assert.match(p.elements.get('status').textContent, /KernelSU GXR/);
});

test('capture is explicit, responsive, and enables native playback only when a valid clip is reported', async () => {
    const p = page(); await flush();
    assert.equal(p.commands.length, 1);
    assert.equal(p.elements.get('play-recording').disabled, true);
    p.elements.get('record').events.click(); await flush();
    assert.equal(p.commands.length, 1);
    assert.match(p.elements.get('test-status').textContent, /Virtual Desktop only off/);
    p.elements.get('vd-only').checked = false;
    p.state.deferRecording = true;
    p.elements.get('record').events.click(); await flush();
    assert.match(p.elements.get('test-status').textContent, /Recording for 10 seconds/);
    assert.equal(p.elements.get('record').disabled, true);
    assert.equal(p.elements.get('play-recording').disabled, true);
    p.state.finishRecording(); await flush();
    assert.equal(p.elements.get('record').disabled, false);
    assert.equal(p.elements.get('play-recording').disabled, false);
    p.elements.get('delete-recording').events.click(); await flush();
    assert.equal(p.elements.get('play-recording').disabled, true);
    assert.equal(p.elements.get('delete-recording').disabled, true);
});

test('native playback keeps Stop available and serializes capture until playback ends', async () => {
    const p = page(); await flush();
    p.elements.get('vd-only').checked = false;
    p.elements.get('record').events.click(); await flush();
    p.state.deferPlayback = true;
    p.elements.get('play-recording').events.click(); await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/settings.sh play');
    assert.equal(p.elements.get('stop-playback').disabled, false);
    assert.equal(p.elements.get('record').disabled, true);
    p.elements.get('stop-playback').events.click(); await flush();
    assert.equal(p.commands.at(-1), 'sh /data/adb/modules/gxr_mic_gain_azj2/settings.sh stop-playback');
    assert.match(p.elements.get('test-status').textContent, /Playback stopped/);
    assert.equal(p.elements.get('record').disabled, false);
    assert.equal(p.elements.get('stop-playback').disabled, true);
});

test('capture errors remain visible and native playback failures report their real error', async () => {
    const p = page(); await flush();
    p.elements.get('vd-only').checked = false;
    p.state.failRecording = true;
    p.elements.get('record').events.click(); await flush();
    assert.match(p.elements.get('test-status').textContent, /Recording failed \(exit 124\)/);
    assert.equal(p.elements.get('play-recording').disabled, true);
    p.state.failRecording = false;
    p.elements.get('record').events.click(); await flush();
    p.state.failPlayback = true;
    p.elements.get('play-recording').events.click(); await flush();
    assert.match(p.elements.get('test-status').textContent, /Native player error/);
    assert.equal(p.elements.get('stop-playback').disabled, true);
});
