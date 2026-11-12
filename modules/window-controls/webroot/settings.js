'use strict';
const modulePath = '/data/adb/modules/gxr_window_curvature';
const keys = ['curvature', 'borderless', 'rotation', 'grab'];
const status = document.getElementById('status');
let request = 0;
let operationBusy = false;

function message(text, error = false) {
    status.textContent = text;
    status.classList.toggle('error', error);
}
function busy(value) {
    operationBusy = value;
    document.getElementById('switches').disabled = value;
    for (const id of ['save', 'start', 'logs']) document.getElementById(id).disabled = value;
}
function exec(command) {
    return new Promise((resolve, reject) => {
        if (!window.ksu || typeof window.ksu.exec !== 'function') {
            reject(new Error('Open this page through KernelSU GXR.'));
            return;
        }
        const callback = 'gxrWindowResult' + (++request);
        const timeout = setTimeout(() => {
            delete window[callback];
            reject(new Error('KernelSU did not respond. Check root status and reopen this page.'));
        }, 45000);
        window[callback] = (code, stdout, stderr) => {
            clearTimeout(timeout);
            delete window[callback];
            if (code === 0) resolve(stdout);
            else reject(new Error(stderr || stdout || 'Command failed.'));
        };
        try { window.ksu.exec(command, '{}', callback); }
        catch (error) { clearTimeout(timeout); delete window[callback]; reject(error); }
    });
}
function showSettings(text) {
    const data = JSON.parse(text);
    showRuntime(data);
    if (!keys.every(key => data[key] === 0 || data[key] === 1) ||
        !['RUNNING', 'STARTING', 'STOPPED', 'DISABLED', 'QUARANTINED'].includes(data.runtime)) {
        throw new Error('The module returned invalid settings.');
    }
    for (const key of keys) document.getElementById(key).checked = data[key] === 1;
    message('Settings loaded.');
    return data;
}
function showRuntime(data) {
    if (!['RUNNING', 'STARTING', 'STOPPED', 'DISABLED', 'QUARANTINED'].includes(data.runtime) ||
        !['off', 'unknown', 'waiting', 'tracking', 'unavailable'].includes(data.grabRuntime)) {
        throw new Error('Invalid runtime status.');
    }
    document.getElementById('runtime').textContent =
        'Runtime: ' + data.runtime.toLowerCase() + ' · Hand tracking: ' + data.grabRuntime +
        (data.runtime === 'STARTING' ? ' · After a Soft restart, waiting for SystemUI’s 90-second startup guard.' : '') +
        (data.grabRuntime === 'waiting' ? ' · No fresh tracked hand pose.' : '');
}
async function perform(action) {
    busy(true);
    try { await action(); }
    catch (error) { message(error.message, true); }
    finally { busy(false); }
}
document.getElementById('features').addEventListener('submit', event => {
    event.preventDefault();
    perform(async () => {
        const values = keys.map(key => document.getElementById(key).checked ? '1' : '0');
        const data = showSettings(await exec('sh ' + modulePath + '/features.sh set ' + values.join(' ')));
        message(data.runtime === 'RUNNING'
            ? 'Saved. Applying to the running module; reopen the window menu.'
            : 'Saved. Enable the module in KernelSU, then start window controls.');
    });
});
document.getElementById('start').addEventListener('click', () => perform(async () => {
    await exec('sh ' + modulePath + '/action.sh start');
    showSettings(await exec('sh ' + modulePath + '/features.sh json'));
}));
document.getElementById('logs').addEventListener('click', () => perform(async () => {
    await exec('sh ' + modulePath + '/recovery.sh export');
    message('Logs exported to /data/local/tmp.');
}));
perform(async () => showSettings(await exec('sh ' + modulePath + '/features.sh json')));
setInterval(async () => {
    if (operationBusy || !window.ksu) return;
    operationBusy = true;
    try { showRuntime(JSON.parse(await exec('sh ' + modulePath + '/features.sh json'))); }
    catch (error) { document.getElementById('runtime').textContent = error.message; }
    finally { operationBusy = false; }
}, 2000);
