import Java from 'frida-java-bridge';

const DEX_BASE64 = '__ROTATION_DEX_BASE64__';
let controller = null;
let bind = null;
let lastPulse = Date.now();
let stopping = false;
let stopReason = '';
let reportedError = false;
let timer;

function stop(reason) {
    if (stopping) return;
    stopping = true;
    stopReason = reason;
    Java.perform(() => {
        if (bind !== null) bind.implementation = null;
        if (controller !== null) controller.shutdown();
    });
}

function fatal(error) {
    console.log('GXR_ROTATION_FATAL ' + String(error.stack || error));
    stop('agent failure');
}

rpc.exports = {
    onFridaStdin(line) {
        if (line.trim() === 'pulse') lastPulse = Date.now();
        if (line.trim() === 'stop') stop('requested');
    },
};

Java.perform(() => {
    try {
        const Menu = Java.use('com.android.wm.shell.windowdecor.XrCaptionMenu');
        const bytes = Java.use('android.util.Base64').decode(DEX_BASE64, 0);
        const loader = Java.use('dalvik.system.InMemoryDexClassLoader').$new(
            Java.use('java.nio.ByteBuffer').wrap(bytes), Menu.class.getClassLoader());
        const factory = Java.ClassFactory.get(loader);
        controller = Java.retain(factory.use('local.gxr.rotation.RotationController').$new());
        bind = Menu.bindMenu.overload();
        bind.implementation = function () {
            const result = bind.call(this);
            if (!stopping) {
                try { controller.onMenu(this); } catch (error) { fatal(error); }
            }
            return result;
        };
        let ticks = 0;
        timer = setInterval(() => Java.perform(() => {
            try {
                if (!stopping && Date.now() - lastPulse > 5000) stop('supervisor timeout');
                if (!stopping) controller.pulse();
                const error = String(controller.getError());
                if (error && !reportedError) {
                    reportedError = true;
                    fatal(error);
                }
                if (stopping && controller.isRestored()) {
                    clearInterval(timer);
                    console.log('GXR_ROTATION_STOPPED ' + stopReason);
                } else if (++ticks % 20 === 0) {
                    console.log('GXR_ROTATION_STATE ' + controller.getStatus());
                }
            } catch (error) { fatal(error); }
        }), 500);
        console.log('GXR_ROTATION_READY');
    } catch (error) { fatal(error); }
});
