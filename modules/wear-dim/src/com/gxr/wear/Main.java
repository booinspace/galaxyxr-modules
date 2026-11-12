package com.gxr.wear;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.IBinder;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import com.gxr.port.PortRuntime;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Properties;

/** Standalone wear/eye observer; blanks only the physical panel, never holds a wake lock. */
public final class Main {
    private static final String KEY = "debug.ix.sysui.eyes_monitor.enabled";
    private static PortRuntime runtime;
    private static Properties state;
    private static Object display, input;
    private static Method retrieve;
    private static DisplayPower panel;
    private static Handler handler;
    private static Field eyeStatus;
    private static SensorManager sensors;
    private static SensorEventListener listener;
    private static PowerManager power;
    private static volatile boolean mounted;
    private static boolean blanked;
    private static final DimPolicy policy = new DimPolicy();
    private static final Runnable POLL = new Runnable() {
        public void run() {
            tick();
            if (!runtime.stopping) handler.postDelayed(this, blanked ? 16 : 250);
        }
    };

    public static void main(String[] args) throws Exception {
        if (args.length != 2 || !(args[0].equals("daemon") || args[0].equals("restore"))) {
            throw new IllegalArgumentException("Expected daemon|restore and module directory");
        }
        runtime = new PortRuntime(args[1]);
        state = runtime.load();
        Looper.prepareMainLooper();
        Class<?> threadType = Class.forName("android.app.ActivityThread");
        Object thread = threadType.getMethod("systemMain").invoke(null);
        Context context = (Context) threadType.getMethod("getSystemContext").invoke(thread);
        display = context.getSystemService(Context.DISPLAY_SERVICE);
        power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        panel = new DisplayPower();
        if (args[0].equals("restore")) {
            restore();
            PortRuntime.log("PORT_STOCK display power and eye-monitor property restored");
            return;
        }
        restoreLegacyBrightness();
        handler = new Handler(Looper.getMainLooper());
        sensors = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        Sensor sensor = sensors.getDefaultSensor(34);
        if (sensor == null) throw new IllegalStateException("Stock off-body sensor unavailable");
        Class<?> inputType = Class.forName("android.graphics.CPM$SystemInputInfo");
        input = inputType.getConstructor(String.class).newInstance("GxrWearDim");
        retrieve = inputType.getMethod("retrieveCurrentSystemInputInfo");
        eyeStatus = inputType.getField("eyesStatus");
        IBinder cpm = (IBinder) Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, "cpm");
        if (cpm == null) throw new IllegalStateException("CPM service unavailable");
        cpm.linkToDeath(() -> runtime.fail(new IllegalStateException("CPM service died")), 0);
        panel.linkToDeath(() -> runtime.fail(new IllegalStateException("Display composer died")));
        listener = new SensorEventListener() {
            public void onSensorChanged(SensorEvent event) {
                mounted = event.values.length > 0 && event.values[0] > 0;
                tick();
            }
            public void onAccuracyChanged(Sensor ignored, int accuracy) { }
        };
        if (!sensors.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL)) {
            throw new IllegalStateException("Could not observe stock wear sensor");
        }
        runtime.watch(Main::restore, null);
        synchronized (Main.class) {
            if (runtime.stopping) throw new IllegalStateException("Runtime stopped during initialization");
            state.setProperty("previousEyeMonitor", PortRuntime.command("/system/bin/getprop", KEY));
            state.setProperty("propertyOwned", "true");
            runtime.save(state);
            PortRuntime.command("/system/bin/setprop", KEY, "false");
            if (!PortRuntime.command("/system/bin/getprop", KEY).equals("false")) {
                throw new IllegalStateException("Eye-monitor property read-back mismatch");
            }
        }
        runtime.ready();
        handler.post(POLL);
        PortRuntime.log("WAITING: 60 seconds without eyes blanks the panel; eye-return polling is 16 ms while blanked");
        Looper.loop();
    }

    private static synchronized void tick() {
        if (runtime.stopping) return;
        try {
            boolean interactive = power.isInteractive();
            long now = SystemClock.elapsedRealtime();
            boolean fresh = mounted && interactive && (Boolean) retrieve.invoke(input);
            int eyes = fresh ? eyeStatus.getInt(input) : 2;
            boolean blank = policy.update(now, mounted, interactive, eyes, fresh);
            if (blank && !blanked) {
                state.setProperty("panelOwned", "true");
                runtime.save(state);
                panel.blank(true);
                blanked = true;
                PortRuntime.log("DISPLAY_BLANKED");
            } else if (!blank && blanked) {
                restorePanel();
            }
        } catch (Exception error) {
            runtime.fail(error);
        }
    }

    private static void restoreLegacyBrightness() throws Exception {
        if (!Boolean.parseBoolean(state.getProperty("brightnessOwned"))) return;
        // NaN releases Android's temporary override and returns control to the user's saved setting.
        Class.forName("android.hardware.display.DisplayManager")
                .getMethod("setTemporaryBrightness", int.class, float.class).invoke(display, 0, Float.NaN);
        state.setProperty("brightnessOwned", "false");
        runtime.save(state);
        PortRuntime.log("BRIGHTNESS_RESTORED");
    }

    private static void restorePanel() throws Exception {
        if (!Boolean.parseBoolean(state.getProperty("panelOwned"))) return;
        // Do not turn the panel on after stock/manual sleep has made Android noninteractive.
        if (power.isInteractive()) {
            panel.blank(false);
            if (!power.isInteractive()) panel.blank(true);
        }
        state.setProperty("panelOwned", "false");
        runtime.save(state);
        blanked = false;
        PortRuntime.log("DISPLAY_RELEASED");
    }

    private static synchronized void restore() throws Exception {
        if (sensors != null && listener != null) sensors.unregisterListener(listener);
        if (handler != null) handler.removeCallbacks(POLL);
        restorePanel();
        restoreLegacyBrightness();
        if (Boolean.parseBoolean(state.getProperty("propertyOwned"))) {
            if (PortRuntime.command("/system/bin/getprop", KEY).equals("false")) {
                String original = state.getProperty("previousEyeMonitor", "");
                PortRuntime.command("/system/bin/setprop", KEY, original);
                if (!PortRuntime.command("/system/bin/getprop", KEY).equals(original)) {
                    throw new IllegalStateException("Eye-monitor property restoration failed");
                }
            }
            state.setProperty("propertyOwned", "false");
            runtime.save(state);
        }
    }
}
