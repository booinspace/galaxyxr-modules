'use strict';
const modulePath = '/data/adb/modules/gxr_root_ft_azj2';
const get = id => document.getElementById(id);
let request = 0;
function exec(command) {
    return new Promise((resolve, reject) => {
        if (typeof window.ksu?.exec !== 'function') return reject(new Error('Open through KernelSU GXR.'));
        const callback = 'gxrRootFace' + (++request);
        const timer = setTimeout(() => { delete window[callback]; reject(new Error('Root command timed out. Reopen Action and check status.')); }, 45000);
        window[callback] = (code, stdout, stderr) => {
            clearTimeout(timer); delete window[callback];
            if (code === 0) resolve(stdout); else reject(new Error(stderr || stdout || 'Command failed.'));
        };
        try { window.ksu.exec(command, '{}', callback); }
        catch (error) { clearTimeout(timer); delete window[callback]; reject(error); }
    });
}
function validPc(value) {
    const parts = value.split('.');
    return parts.length === 4 && parts.every(p => /^(0|[1-9][0-9]{0,2})$/.test(p) && Number(p) <= 255) &&
        Number(parts[0]) > 0 && Number(parts[0]) !== 127 && Number(parts[0]) < 224 && Number(parts[3]) > 0 && Number(parts[3]) < 255;
}
async function perform(command) {
    get('controls').disabled = true;
    get('status').textContent = 'Working…';
    try {
        const text = await exec('sh ' + modulePath + '/control.sh ' + command);
        get('status').textContent = text;
        const address = text.match(/^PC=([0-9.]+) UDP=41463$/m)?.[1];
        if (address && validPc(address)) get('pc').value = address;
    } catch (error) { get('status').textContent = error.message; }
    finally { get('controls').disabled = false; }
}
get('settings').addEventListener('submit', event => {
    event.preventDefault();
    const pc = get('pc').value.trim();
    if (!validPc(pc)) { get('status').textContent = 'Enter one unicast PC IPv4 address.'; return; }
    perform('set-pc ' + pc);
});
for (const [id, command] of [['start', 'start'], ['stop', 'stop'], ['refresh', 'status'], ['logs', 'export']]) {
    get(id).addEventListener('click', () => perform(command));
}
perform('status');
