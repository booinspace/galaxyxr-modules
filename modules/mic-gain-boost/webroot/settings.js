'use strict';
const modulePath = '/data/adb/modules/gxr_mic_gain_azj2';
const get = id => document.getElementById(id);
let request = 0;

function message(text, error = false) {
    get('status').textContent = text;
    get('status').classList.toggle('error', error);
}
function busy(value) {
    get('controls').disabled = value;
    for (const id of ['apply', 'start', 'logs']) get(id).disabled = value;
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
        ![0, 1].includes(data.vdOnly) || typeof data.running !== 'boolean') {
        throw new Error('The module returned invalid mic settings.');
    }
    get('gain').value = String(data.gain);
    get('gain-value').textContent = '+' + data.gain + ' steps';
    get('vd-only').checked = data.vdOnly === 1;
    message(data.running ? 'Mic boost is running.' : 'Enable this module in KernelSU, then tap Start mic boost.');
    return data;
}
async function perform(action) {
    busy(true);
    try { await action(); }
    catch (error) { message(error.message, true); }
    finally { busy(false); }
}
get('gain').addEventListener('input', () => {
    get('gain-value').textContent = '+' + get('gain').value + ' steps';
});
get('settings').addEventListener('submit', event => {
    event.preventDefault();
    perform(async () => {
        const gain = Number(get('gain').value);
        if (!Number.isInteger(gain) || gain < 0 || gain > 40) throw new Error('Gain must be 0–40.');
        const data = showSettings(await exec('sh ' + modulePath + '/settings.sh set ' + gain +
            ' ' + (get('vd-only').checked ? '1' : '0')));
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
perform(async () => showSettings(await exec('sh ' + modulePath + '/settings.sh json')));
