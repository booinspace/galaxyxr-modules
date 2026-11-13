'use strict';
const pinButtons = ['pin-app', 'pin-minimize', 'pin-restore', 'pin-close-all'];
const pinPackage = document.getElementById('pin-package');
for (const [id, action] of [['pin-app', 'pin'], ['pin-minimize', 'minimize'],
                          ['pin-restore', 'restore'], ['pin-close-all', 'close-all']]) {
    document.getElementById(id).addEventListener('click', async () => {
        if (operationBusy) return;
        const pkg = pinPackage.value.trim();
        if (action === 'pin' && (pkg.length > 200 ||
                !/^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$/.test(pkg))) {
            message('Enter an installed app package, such as app.symfonik.music.player.', true);
            return;
        }
        pinButtons.forEach(button => { document.getElementById(button).disabled = true; });
        try {
            await perform(async () => {
                const result = await exec('sh ' + modulePath + '/pins.sh ' + action +
                    (action === 'pin' ? ' ' + pkg : ''));
                if (action === 'pin') message('Pinned. Open Steam Link; the app should remain over it. ' +
                    'This experimental overlay still needs headset testing.');
                else if (action === 'minimize') message('Minimise requested. Restore brings the pinned window back.');
                else if (action === 'restore') message('Restore requested.');
                else message(result.trim());
            });
        } finally {
            pinButtons.forEach(button => { document.getElementById(button).disabled = false; });
        }
    });
}
