/* Adapted from BreadDoesStuff/galaxy-xr-modules, MIT; see LICENSE.upstream. */
package com.gxr.mic;

import android.media.AudioRecordingConfiguration;
import android.media.IAudioService;
import android.media.IRecordingConfigDispatcher;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.ServiceManager;
import com.gxr.port.PortRuntime;
import java.io.File;
import java.io.FileInputStream;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Properties;

/** Event-driven gain for the built-in mic path, with live global/VD-only settings. */
public final class Main {
    private static final String CTL = "TX_DEC0 Volume";
    private static final long[] RECHECK_MS = {0, 150, 500, 1500, 4000};
    private static final GainState gain = new GainState();
    private static int mode = 1;
    private static int gainDb = 15;
    private static Handler handler;
    private static IAudioService audio;
    private static PortRuntime runtime;
    private static Method packageName;
    private static volatile boolean want;
    private static final Runnable APPLY = () -> {
        try { apply(want && !runtime.stopping); }
        catch (Exception error) { runtime.fail(error); }
    };

    @SuppressWarnings("deprecation")
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Expected daemon|restore and module directory");
        runtime = new PortRuntime(args[1]);
        loadState(readCtl());
        if ("restore".equals(args[0])) {
            restore();
            PortRuntime.log("PORT_STOCK mic gain restored or already changed by audio HAL");
            return;
        }
        if (!"daemon".equals(args[0])) throw new IllegalArgumentException("Unknown mode");
        loadConfig();
        packageName = AudioRecordingConfiguration.class.getMethod("getClientPackageName");
        Looper.prepareMainLooper();
        handler = new Handler(Looper.getMainLooper());
        runtime.watch(Main::restore, () -> handler.post(Main::reloadConfig));
        IBinder binder = null;
        for (int retry = 0; binder == null && retry < 30 && !runtime.stopping; retry++) {
            binder = ServiceManager.getService("audio");
            if (binder == null) Thread.sleep(500);
        }
        if (binder == null) throw new IllegalStateException("AudioService unavailable");
        audio = IAudioService.Stub.asInterface(binder);
        binder.linkToDeath(() -> runtime.fail(new IllegalStateException("AudioService died")), 0);
        audio.registerRecordingCallback(new IRecordingConfigDispatcher.Stub() {
            @Override public void dispatchRecordingConfigChange(List<AudioRecordingConfiguration> configs) {
                handler.post(() -> update(configs));
            }
        });
        update(audio.getActiveRecordingConfigurations());
        runtime.ready();
        Looper.loop();
    }

    private static boolean loadConfig() throws Exception {
        Properties config = new Properties();
        try (FileInputStream input = new FileInputStream(new File(runtime.module, "config.conf"))) { config.load(input); }
        int nextMode = Integer.parseInt(config.getProperty("MODE", "1").trim());
        int nextGain = Integer.parseInt(config.getProperty("GAIN_DB", "15").trim());
        GainState.wanted(false, false, nextMode);
        gain.target(false, 0, nextGain);
        boolean changed = mode != nextMode || gainDb != nextGain;
        mode = nextMode;
        gainDb = nextGain;
        return changed;
    }

    private static void reloadConfig() {
        if (runtime.stopping || audio == null) return;
        try {
            if (loadConfig()) {
                PortRuntime.log("SETTINGS mode=" + mode + " gainSteps=" + gainDb);
                updateChecked(audio.getActiveRecordingConfigurations());
            }
        } catch (Exception error) { runtime.fail(error); }
    }

    private static void update(List<AudioRecordingConfiguration> configs) {
        try { updateChecked(configs); }
        catch (Exception error) { runtime.fail(error); }
    }

    private static void updateChecked(List<AudioRecordingConfiguration> configs) throws Exception {
        if (runtime.stopping) return;
        boolean vd = false, other = false;
        if (configs != null) for (AudioRecordingConfiguration config : configs) {
            if (config.isClientSilenced()) continue;
            int source = config.getClientAudioSource();
            if (GainState.eligible((String) packageName.invoke(config), source, false)) vd = true;
            else if (GainState.otherMic(source)) other = true;
        }
        want = GainState.wanted(vd, other, mode);
        PortRuntime.log("capture eligible=" + vd + " concurrent=" + other + " boost=" + want);
        handler.removeCallbacks(APPLY);
        for (long delay : RECHECK_MS) handler.postDelayed(APPLY, delay);
    }

    private static synchronized void apply(boolean boost) throws Exception {
        int current = readCtl();
        int target = gain.target(boost, current, gainDb);
        if (boost && target != current) {
            gain.own(current, target);
            saveState(); // Journal before writing so a killed process cannot lose ownership.
            writeCtl(target);
        } else if (!boost && gain.written >= 0) {
            if (target != current) writeCtl(target);
            gain.clear();
            saveState();
        }
    }

    private static synchronized void restore() throws Exception {
        want = false;
        if (handler != null) handler.removeCallbacks(APPLY);
        apply(false);
    }

    private static void loadState(int current) throws Exception {
        Properties state = runtime.load();
        if (!"mic".equals(state.getProperty("kind"))) return;
        int saved = Integer.parseInt(state.getProperty("saved", "-1"));
        int written = Integer.parseInt(state.getProperty("written", "-1"));
        if (saved >= 0 && saved <= 124 && written >= saved && written <= 124 && current == written) {
            gain.own(saved, written);
        }
    }

    private static void saveState() throws Exception {
        Properties state = new Properties();
        state.setProperty("kind", "mic");
        state.setProperty("saved", Integer.toString(gain.saved));
        state.setProperty("written", Integer.toString(gain.written));
        runtime.save(state);
    }

    private static int readCtl() throws Exception {
        String value = PortRuntime.command("/system/bin/tinymix", "-D", "0", "-v", CTL);
        if (!value.matches("[0-9]{1,3}")) throw new IllegalStateException("Expected one numeric mixer value: " + value);
        int current = Integer.parseInt(value);
        if (current > 124) throw new IllegalStateException("Unsupported mixer range");
        return current;
    }

    private static void writeCtl(int value) throws Exception {
        PortRuntime.command("/system/bin/tinymix", "-D", "0", CTL, Integer.toString(value));
        if (readCtl() != value) throw new IllegalStateException("Mixer write did not read back correctly");
        PortRuntime.log("TX_DEC0=" + value);
    }
}
