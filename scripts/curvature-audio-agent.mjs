/** Shares Window Controls' patched ART bridge and injector. */
export function installAudioMixer(Java, factory, report) {
    let mixer = null;
    let stopping = false;
    let setupFailed = false;
    const hooks = [];
    try {
        const Type = factory.use('local.gxr.audio.AudioMixer');
        const application = Java.use('android.app.ActivityThread').currentApplication();
        if (application === null) throw new Error('SystemUI application unavailable');
        mixer = Java.retain(Type.$new(application.getApplicationContext()));
        const Popup = Java.use('com.android.systemui.volume.VolumeDialogImpl');
        const show = Popup.showH.overload('int', 'boolean', 'int');
        show.implementation = function (reason, locked, mode) {
            const result = show.call(this, reason, locked, mode);
            if (!stopping) {
                try { mixer.attach(this.mDialog.value, false, this); }
                catch (error) { report('AUDIO_MIXER_UI_ERROR', {error: String(error)}); }
            }
            return result;
        };
        hooks.push(show);
        const Expanded = Java.use('com.android.systemui.volume.VolumePanelDialog');
        const create = Expanded.onCreate.overload('android.os.Bundle');
        create.implementation = function (state) {
            const result = create.call(this, state);
            if (!stopping) {
                try { mixer.attach(this, true, null); }
                catch (error) { report('AUDIO_MIXER_UI_ERROR', {error: String(error)}); }
            }
            return result;
        };
        hooks.push(create);
        mixer.start();
        report('AUDIO_MIXER_READY', {panels: ['popup', 'expanded']});
    } catch (error) {
        setupFailed = true;
        for (const hook of hooks) hook.implementation = null;
        hooks.length = 0;
        if (mixer !== null) mixer.stop();
        report('AUDIO_MIXER_UNAVAILABLE', {error: String(error)});
    }
    return {
        stop() {
            stopping = true;
            for (const hook of hooks) hook.implementation = null;
            hooks.length = 0;
            if (mixer !== null) mixer.stop();
        },
        isStopped() { return mixer === null || mixer.isStopped(); },
        status() { return setupFailed ? 'unavailable' : mixer === null ? 'stopped' : String(mixer.status()); },
    };
}
