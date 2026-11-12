package com.gxr.wear;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import com.gxr.port.PortRuntime;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Properties;

/** Standalone wear/eye observer; owns one temporary brightness override, never a wake lock. */
public final class Main {
    private static final String KEY = "debug.ix.sysui.eyes_monitor.enabled";
    private static PortRuntime runtime;
    private static Properties state;
    private static Object display, input;
    private static Method temporaryBrightness, brightness, retrieve;
    private static Field eyeStatus;
    private static SensorManager sensors;
    private static SensorEventListener listener;
    private static PowerManager power;
    private static volatile boolean mounted;
    private static int eyes = -1;
    private static boolean attemptedDim;
    private static final DimPolicy policy = new DimPolicy();

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
        Class<?> displayType = Class.forName("android.hardware.display.DisplayManager");
        temporaryBrightness = displayType.getMethod("setTemporaryBrightness", int.class, float.class);
        brightness = displayType.getMethod("getBrightness", int.class);
        if (args[0].equals("restore")) {
            restore();
            PortRuntime.log("PORT_STOCK brightness and eye-monitor property restored");
            return;
        }
        sensors = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
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
        listener = new SensorEventListener() {
            public void onSensorChanged(SensorEvent event) {
                mounted = event.values.length > 0 && event.values[0] > 0;
            }
            public void onAccuracyChanged(Sensor ignored, int accuracy) { }
        };
        if (!sensors.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL)) {
            throw new IllegalStateException("Could not observe stock wear sensor");
        }
        runtime.watch(Main::restore, Main::tick);
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
        PortRuntime.log("WAITING: wear headset; 60 seconds without eyes dims to 20% of current brightness");
        Looper.loop();
    }

    private static synchronized void tick() {
        if (runtime.stopping) return;
        try {
            boolean interactive = power.isInteractive();
            if (!mounted || !interactive) eyes = -1;
            else if ((Boolean) retrieve.invoke(input)) eyes = eyeStatus.getInt(input);
            // A false retrieval leaves the last observation intact, as in stock EyesMonitor's StateFlow.
            boolean dim = policy.update(SystemClock.elapsedRealtime(), mounted, interactive, eyes);
            if (dim && !attemptedDim) {
                float current = ((Number) brightness.invoke(display, 0)).floatValue();
                float target = DimPolicy.dimLevel(current);
                if (target < current) {
                    state.setProperty("brightnessOwned", "true");
                    runtime.save(state);
                    temporaryBrightness.invoke(display, 0, target);
                    PortRuntime.log("DIMMED " + current + " -> " + target);
                } else {
                    PortRuntime.log("DIM_SKIPPED: display already at minimum brightness");
                }
                attemptedDim = true;
            } else if (!dim && attemptedDim) {
                restoreBrightness();
                attemptedDim = false;
            }
        } catch (Exception error) {
            runtime.fail(error);
        }
    }

    private static void restoreBrightness() throws Exception {
        if (!Boolean.parseBoolean(state.getProperty("brightnessOwned"))) return;
        // NaN releases Android's temporary override and returns control to the user's saved setting.
        temporaryBrightness.invoke(display, 0, Float.NaN);
        state.setProperty("brightnessOwned", "false");
        runtime.save(state);
        PortRuntime.log("BRIGHTNESS_RESTORED");
    }

    private static synchronized void restore() throws Exception {
        if (sensors != null && listener != null) sensors.unregisterListener(listener);
        restoreBrightness();
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
