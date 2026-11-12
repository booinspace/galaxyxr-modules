'use strict';
const modulePath = '/data/adb/modules/gxr_mic_gain_azj2';
const get = id => document.getElementById(id);
let request = 0;
let hasRecording = false;
let working = false;
let playing = false;
let stopping = false;

function message(text, error = false, id = 'status') {
    get(id).textContent = text;
    get(id).classList.toggle('error', error);
}
function playbackButtons() {
    get('play-recording').disabled = working || !hasRecording;
    get('stop-playback').disabled = !playing || stopping;
}
function busy(value) {
    working = value;
    get('controls').disabled = value;
    for (const id of ['apply', 'start', 'logs', 'record']) get(id).disabled = value;
    get('delete-recording').disabled = value || !hasRecording;
    if (!value) get('record').textContent = 'Record 10 seconds';
    playbackButtons();
}
function spawn(command) {
    return new Promise((resolve, reject) => {
        if (!window.ksu || typeof window.ksu.spawn !== 'function') {
            reject(new Error('The microphone test requires KernelSU GXR with the spawn bridge.'));
            return;
        }
        const callback = 'gxrMicCapture' + (++request);
        let stdout = '', stderr = '', finished = false;
        const finish = code => {
            if (finished) return;
            finished = true;
            clearTimeout(timer);
            // GXR can send an error event immediately after its exit event.
            setTimeout(() => { delete window[callback]; }, 1000);
            if (code === 0) resolve(stdout);
            else reject(new Error(stderr || 'Microphone test failed. Check root and audio status.'));
        };
        const timer = setTimeout(() => {
            stderr = 'The audio helper did not respond. Reopen Action and check root status.';
            finish(1);
        }, 30000);
        window[callback] = {
            stdout: {emit(event, text) { stdout = (stdout + text + '\n').slice(-8192); }},
            stderr: {emit(event, text) { stderr = (stderr + text + '\n').slice(-8192); }},
            emit(event, value) {
                if (event === 'exit') finish(value);
                else if (event === 'error') { stderr = value.message || stderr; finish(1); }
            }
        };
        try {
            window.ksu.spawn('sh', JSON.stringify([modulePath + '/settings.sh', command]), '{}', callback);
        } catch (error) { stderr = error.message; finish(1); }
    });
}
function exec(command) {
    return new Promise((resolve, reject) => {
        if (!window.ksu || typeof window.ksu.exec !== 'function') {
            reject(new Error('Open this page through KernelSU GXR.'));
            return;
        }
        const callback = 'gxrMicResult' + (++request);
        const timer = setTimeout(() => {
            delete window[callback];
            reject(new Error('KernelSU did not respond. Check root status and reopen this page.'));
        }, 45000);
        window[callback] = (code, stdout, stderr) => {
            clearTimeout(timer);
            delete window[callback];
            if (code === 0) resolve(stdout);
            else reject(new Error(stderr || stdout || 'Command failed.'));
        };
        try { window.ksu.exec(command, '{}', callback); }
        catch (error) { clearTimeout(timer); delete window[callback]; reject(error); }
    });
}
function showSettings(text) {
    const data = JSON.parse(text);
    if (!Number.isInteger(data.gain) || data.gain < 0 || data.gain > 40 ||
        ![0, 1].includes(data.vdOnly) || typeof data.running !== 'boolean' || typeof data.recording !== 'boolean') {
        throw new Error('The module returned invalid mic settings.');
    }
    get('gain').value = String(data.gain);
    get('gain-value').textContent = '+' + data.gain + ' steps';
    get('vd-only').checked = data.vdOnly === 1;
    hasRecording = data.recording;
    message(hasRecording ? 'Recording available. Tap Play recording.' : 'No recording yet. Record a clip to enable playback.', false, 'test-status');
    playbackButtons();
    message(data.running ? 'Mic boost is running.' : 'Enable this module in KernelSU, then tap Start mic boost.');
    return data;
}
async function saveSettings() {
    const gain = Number(get('gain').value);
    if (!Number.isInteger(gain) || gain < 0 || gain > 40) throw new Error('Gain must be 0–40.');
    return showSettings(await exec('sh ' + modulePath + '/settings.sh set ' + gain +
        ' ' + (get('vd-only').checked ? '1' : '0')));
}
async function perform(action, statusId = 'status') {
    busy(true);
    try { await action(); }
    catch (error) { message(error.message, true, statusId); }
    finally { busy(false); }
}
get('gain').addEventListener('input', () => {
    get('gain-value').textContent = '+' + get('gain').value + ' steps';
});
get('settings').addEventListener('submit', event => {
    event.preventDefault();
    perform(async () => {
        const data = await saveSettings();
        message(data.running ? 'Saved. Applying to active recordings.' : 'Saved. Enable the module, then tap Start mic boost.');
    });
});
get('start').addEventListener('click', () => perform(async () => {
    await exec('sh ' + modulePath + '/control.sh action');
    showSettings(await exec('sh ' + modulePath + '/settings.sh json'));
}));
get('logs').addEventListener('click', () => perform(async () => {
    await exec('sh ' + modulePath + '/control.sh export');
    message('Status checked; logs exported to /data/local/tmp.');
}));
get('record').addEventListener('click', () => perform(async () => {
    if (get('vd-only').checked) throw new Error('Turn Virtual Desktop only off to hear boost in this test.');
    message('Preparing microphone test…', false, 'test-status');
    const data = await saveSettings();
    if (!data.running) throw new Error('Enable and start mic boost first.');
    get('record').textContent = 'Recording…';
    message('Recording for 10 seconds… Speak normally.', false, 'test-status');
    showSettings(await spawn('record'));
    message('Recording saved. Tap Play recording to listen.', false, 'test-status');
}, 'test-status'));
get('delete-recording').addEventListener('click', () => perform(async () => {
    showSettings(await exec('sh ' + modulePath + '/settings.sh delete-recording'));
    message('Recording deleted.', false, 'test-status');
}, 'test-status'));
get('play-recording').addEventListener('click', () => perform(async () => {
    if (!hasRecording) return;
    playing = true;
    stopping = false;
    playbackButtons();
    message('Playing recording.', false, 'test-status');
    try {
        await spawn('play');
        message(stopping ? 'Playback stopped.' : 'Playback finished.', false, 'test-status');
    } finally { playing = false; stopping = false; }
}, 'test-status'));
get('stop-playback').addEventListener('click', async () => {
    if (!playing || stopping) return;
    stopping = true;
    message('Stopping playback…', false, 'test-status');
    playbackButtons();
    try { await exec('sh ' + modulePath + '/settings.sh stop-playback'); }
    catch (error) { stopping = false; message(error.message, true, 'test-status'); playbackButtons(); }
});
perform(async () => showSettings(await exec('sh ' + modulePath + '/settings.sh json')));
