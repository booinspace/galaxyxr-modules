'use strict';
const gestureForm = document.getElementById('quick-settings-gesture');
const gestureEnabled = document.getElementById('quick-settings-enabled');
const gestureHold = document.getElementById('quick-settings-hold');
const gestureOptions = document.getElementById('quick-settings-options');
const gestureSave = document.getElementById('quick-settings-save');

function gestureBusy(value) {
    gestureOptions.disabled = value;
    gestureSave.disabled = value;
}
function showGestureSettings(text) {
    const data = JSON.parse(text);
    if (![0, 1].includes(data.enabled) || ![0, 500].includes(data.holdMs)) {
        throw new Error('Invalid pinch shortcut settings.');
    }
    gestureEnabled.checked = data.enabled === 1;
    gestureHold.value = String(data.holdMs);
}
gestureForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (gestureSave.disabled) return;
    const hold = gestureHold.value;
    if (!['0', '500'].includes(hold)) { message('Choose a supported pinch trigger.', true); return; }
    gestureBusy(true);
    try {
        showGestureSettings(await exec('sh ' + modulePath + '/quick-settings-gesture.sh set ' +
            (gestureEnabled.checked ? '1' : '0') + ' ' + hold));
        message('Pinch settings saved. The shortcut follows these settings while Window Controls is running.');
    } catch (error) { message(error.message, true); }
    finally { gestureBusy(false); }
});
(async () => {
    try {
        showGestureSettings(await exec('sh ' + modulePath + '/quick-settings-gesture.sh json'));
        gestureBusy(false);
    } catch (error) { message(error.message, true); }
})();
