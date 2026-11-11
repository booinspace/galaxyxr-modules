/* Adapted from BreadDoesStuff/galaxy-xr-modules, MIT; see LICENSE.upstream. */
package com.gxr.pt;

import com.gxr.port.PortRuntime;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Event-driven physical double-tap passthrough, with explicit state ownership. */
public final class Main {
    private static PortRuntime runtime;
    private static Constructor<?> updatesConstructor;
    private static Method getNode, setAlpha, setZ, setVisible, apply;
    private static float alpha = 1;
    private static int z = 9999;
    private static int debounce = 600;
    private static boolean enabled = true, muteToast;
    private static boolean known, owned, toastMuted;
    private static float sysAlpha;
    private static int sysZ;
    private static long lastPush = -1, lastToggle, toastEnd;
    private static String sysui, previousToast;
    private static volatile boolean fullSpace;
    private static Object taskManager;
    private static Method focused;
    private static Process follower;
    private static final Object focusLock = new Object();

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Expected daemon|restore and module directory");
        runtime = new PortRuntime(args[1]);
        initCpm();
        loadState();
        if ("restore".equals(args[0])) {
            restore();
            PortRuntime.log("PORT_STOCK passthrough ownership and toast setting restored");
            return;
        }
        if (!"daemon".equals(args[0])) throw new IllegalArgumentException("Unknown mode");
        restore();
        loadConfig();
        known = false;
        sysui = System.getenv("GXR_SYSUI_ID");
        if (sysui == null || !sysui.equals(currentSysui())) throw new IllegalStateException("SystemUI identity unavailable");
        initFocus();
        final long started = System.currentTimeMillis();
        String since = new SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US).format(new Date(started));
        bootstrap();
        runtime.watch(Main::restore, () -> {
            try { command(); } catch (Exception error) { runtime.fail(error); }
        });
        Thread tracker = new Thread(() -> {
            while (!runtime.stopping) {
                try {
                    evaluate();
                    synchronized (focusLock) { focusLock.wait(1000); }
                } catch (Exception error) { runtime.fail(error); }
            }
        }, "passthrough-focus");
        tracker.setDaemon(true);
        tracker.start();
        runtime.ready();
        String pid = sysui.split(":")[1];
        follower = new ProcessBuilder("/system/bin/logcat", "--pid=" + pid, "-v", "epoch", "-T", since,
                "-s", "OnDeviceTouchpadInputEventReceiver:D", "SceneTransactionProcessorImpl:D")
                .redirectErrorStream(true).start();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(follower.getInputStream()))) {
            for (String line; !runtime.stopping && (line = reader.readLine()) != null;) {
                long time = PassthroughPolicy.timestamp(line);
                observe(line, time);
                if (time >= started && line.contains(PassthroughPolicy.REJECT)) {
                    synchronized (Main.class) {
                        toastEnd = Math.min(System.currentTimeMillis() + 60000,
                                Math.max(toastEnd, System.currentTimeMillis()) + 4600);
                    }
                    if (enabled) toggle();
                }
            }
            if (!runtime.stopping) runtime.fail(new IllegalStateException("SystemUI log stream ended"));
            while (true) Thread.sleep(1000);
        }
    }

    private static void initCpm() throws Exception {
        Class<?> node = Class.forName("android.graphics.CPM$Node");
        Class<?> updates = Class.forName("android.graphics.CPM$NodeUpdates");
        updatesConstructor = updates.getConstructor();
        getNode = Class.forName("android.graphics.CPM").getMethod("getPassthroughNode");
        setAlpha = updates.getMethod("setAlpha", node, float.class);
        setZ = updates.getMethod("setZ", node, int.class);
        setVisible = updates.getMethod("setVisible", node, boolean.class);
        apply = updates.getMethod("apply");
    }

    private static void update(float value, int order) throws Exception {
        try (AutoCloseable node = (AutoCloseable) getNode.invoke(null);
             AutoCloseable updates = (AutoCloseable) updatesConstructor.newInstance()) {
            setAlpha.invoke(updates, node, value);
            setZ.invoke(updates, node, order);
            setVisible.invoke(updates, node, value > 0);
            apply.invoke(updates);
        }
    }

    private static synchronized void toggle() throws Exception {
        long now = System.nanoTime() / 1000000;
        if (now - lastToggle < debounce) return;
        lastToggle = now;
        if (!owned) {
            if (!fullSpace || !known) {
                PortRuntime.log("WAITING: need an immersive app and an observed SystemUI passthrough state");
                return;
            }
            if (!sysui.equals(currentSysui())) throw new IllegalStateException("SystemUI changed");
            owned = true;
            saveState();
            update(alpha, z);
            PortRuntime.log("passthrough ON");
        } else {
            returnControl();
            PortRuntime.log("passthrough returned to SystemUI baseline");
        }
    }

    private static synchronized void returnControl() throws Exception {
        if (!owned) return;
        if (!known || !sysui.equals(currentSysui())) throw new IllegalStateException("Cannot verify current SystemUI owner; full reboot required");
        update(sysAlpha, sysZ);
        owned = false;
        saveState();
    }

    private static synchronized void observe(String line, long time) throws Exception {
        PassthroughPolicy.Push state = PassthroughPolicy.push(line);
        if (state != null && time < 0) throw new IllegalStateException("Unrecognized logcat timestamp");
        if (state == null || time < lastPush || runtime.stopping) return;
        lastPush = time;
        sysAlpha = state.alpha;
        sysZ = state.z;
        known = true;
        // SystemUI has submitted its own transaction, so stop claiming this node.
        owned = false;
        saveState();
    }

    private static void bootstrap() throws Exception {
        Process process = new ProcessBuilder("/system/bin/logcat", "-d", "--pid=" + sysui.split(":")[1],
                "-v", "epoch", "-s", "SceneTransactionProcessorImpl:D").redirectErrorStream(true).start();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            for (String line; (line = reader.readLine()) != null;) observe(line, PassthroughPolicy.timestamp(line));
        } finally { process.destroy(); }
    }

    private static final class Listener extends android.app.TaskStackListener {
        @Override public void onTaskStackChanged() { synchronized (focusLock) { focusLock.notifyAll(); } }
    }

    private static void initFocus() throws Exception {
        taskManager = Class.forName("android.app.ActivityTaskManager").getMethod("getService").invoke(null);
        Class<?> type = Class.forName("android.app.IActivityTaskManager");
        focused = type.getMethod("getFocusedRootTaskInfo");
        type.getMethod("registerTaskStackListener", Class.forName("android.app.ITaskStackListener"))
                .invoke(taskManager, new Listener());
    }

    private static void evaluate() throws Exception {
        if (!sysui.equals(currentSysui())) throw new IllegalStateException("SystemUI process changed");
        Object info = focused.invoke(taskManager);
        boolean immersive = false;
        if (info != null) {
            Object config = info.getClass().getField("configuration").get(info);
            Object window = config.getClass().getField("windowConfiguration").get(config);
            immersive = (Integer) window.getClass().getMethod("getComputedXrDesktopMode").invoke(window) == 2;
        }
        synchronized (Main.class) {
            fullSpace = immersive;
            if (!immersive) returnControl();
            if (muteToast && immersive) mute();
            else if (System.currentTimeMillis() >= toastEnd) unmute();
        }
    }

    private static void command() throws Exception {
        File file = new File(runtime.runtime, "command");
        if (!file.isFile()) return;
        String command = new String(Files.readAllBytes(file.toPath()), StandardCharsets.US_ASCII).trim();
        if (!file.delete()) throw new IllegalStateException("Could not consume command");
        if ("toggle".equals(command)) { synchronized (Main.class) { lastToggle = 0; toggle(); } }
        else throw new IllegalArgumentException("Unsupported control command");
    }

    private static String currentSysui() throws Exception {
        String pid = PortRuntime.command("/system/bin/pidof", "com.android.systemui");
        if (!pid.matches("[0-9]+")) throw new IllegalStateException("Expected one SystemUI process");
        String stat = new String(Files.readAllBytes(new File("/proc/" + pid + "/stat").toPath()), StandardCharsets.US_ASCII);
        String start = stat.substring(stat.lastIndexOf(')') + 2).split(" ")[19];
        return PortRuntime.boot() + ":" + pid + ":" + start;
    }

    private static String toastMode() throws Exception {
        String result = PortRuntime.command("/system/bin/cmd", "appops", "get", "com.android.systemui", "TOAST_WINDOW");
        Matcher match = Pattern.compile("TOAST_WINDOW:\\s*(allow|ignore|deny|default|foreground)\\b").matcher(result);
        if (match.find()) return match.group(1);
        if (result.toLowerCase(Locale.US).contains("no operations")) return "default";
        throw new IllegalStateException("Unrecognized original toast app-op");
    }

    private static void mute() throws Exception {
        if (toastMuted) return;
        previousToast = toastMode();
        toastMuted = true;
        saveState();
        PortRuntime.command("/system/bin/cmd", "appops", "set", "com.android.systemui", "TOAST_WINDOW", "ignore");
    }

    private static void unmute() throws Exception {
        if (!toastMuted) return;
        if ("ignore".equals(toastMode())) {
            if (previousToast == null || !previousToast.matches("allow|ignore|deny|default|foreground")) {
                throw new IllegalStateException("Invalid saved toast app-op");
            }
            PortRuntime.command("/system/bin/cmd", "appops", "set", "com.android.systemui", "TOAST_WINDOW", previousToast);
        }
        toastMuted = false;
        saveState();
    }

    private static synchronized void restore() throws Exception {
        if (follower != null) follower.destroy();
        Exception failure = null;
        try { returnControl(); } catch (Exception error) { failure = error; }
        try { unmute(); } catch (Exception error) {
            if (failure == null) failure = error; else failure.addSuppressed(error);
        }
        if (failure != null) throw failure;
    }

    private static void loadState() throws Exception {
        Properties state = runtime.load();
        if (!"passthrough".equals(state.getProperty("kind"))) return;
        owned = Boolean.parseBoolean(state.getProperty("owned", "false"));
        known = Boolean.parseBoolean(state.getProperty("known", "false"));
        sysAlpha = Float.parseFloat(state.getProperty("alpha", "0"));
        sysZ = Integer.parseInt(state.getProperty("z", "-2"));
        sysui = state.getProperty("sysui");
        toastMuted = Boolean.parseBoolean(state.getProperty("toastMuted", "false"));
        previousToast = state.getProperty("toastPrevious");
        if (!Float.isFinite(sysAlpha) || sysAlpha < 0 || sysAlpha > 1) throw new IllegalStateException("Invalid saved alpha");
    }

    private static void saveState() throws Exception {
        Properties state = new Properties();
        state.setProperty("kind", "passthrough");
        state.setProperty("owned", Boolean.toString(owned));
        state.setProperty("known", Boolean.toString(known));
        state.setProperty("alpha", Float.toString(sysAlpha));
        state.setProperty("z", Integer.toString(sysZ));
        state.setProperty("sysui", sysui == null ? "" : sysui);
        state.setProperty("toastMuted", Boolean.toString(toastMuted));
        state.setProperty("toastPrevious", previousToast == null ? "" : previousToast);
        runtime.save(state);
    }

    private static void loadConfig() throws Exception {
        Properties config = new Properties();
        try (FileInputStream input = new FileInputStream(new File(runtime.module, "config.conf"))) { config.load(input); }
        alpha = Float.parseFloat(config.getProperty("ALPHA", "1.0").trim());
        z = Integer.parseInt(config.getProperty("Z", "9999").trim());
        debounce = Integer.parseInt(config.getProperty("DEBOUNCE_MS", "600").trim());
        String enabledValue = config.getProperty("ENABLED", "1").trim();
        String toastValue = config.getProperty("MUTE_SYSUI_TOAST", "0").trim();
        if (!enabledValue.matches("[01]") || !toastValue.matches("[01]")) {
            throw new IllegalArgumentException("ENABLED and MUTE_SYSUI_TOAST must be 0 or 1");
        }
        enabled = "1".equals(enabledValue);
        muteToast = "1".equals(toastValue);
        if (!Float.isFinite(alpha) || alpha < 0 || alpha > 1 || z < -10000 || z > 10000
                || debounce < 100 || debounce > 5000) throw new IllegalArgumentException("Invalid passthrough configuration");
    }
}
