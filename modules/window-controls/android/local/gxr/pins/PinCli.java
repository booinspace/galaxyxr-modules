package local.gxr.pins;

import android.app.ActivityManager.RunningTaskInfo;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Process;
import android.os.Looper;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import java.lang.reflect.Method;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;

/** Root-only launcher and task controls for explicitly marked, user-selected overlay windows. */
public final class PinCli {
    public static final String MARKER = "boo.puppy.gxr.PINNED_OVERLAY";

    /** A private-process fixture for the read-only on-device cleanup check. */
    public static final class CheckOwner {
        private final Handler mainHandler;
        volatile boolean closed;
        CheckOwner(Handler handler) { mainHandler = handler; }
        public void destroyWindowDecoration(RunningTaskInfo ignored) {
            if (Looper.myLooper() != mainHandler.getLooper()) throw new IllegalStateException("Wrong caption thread");
            closed = true;
        }
    }

    private static Object invoke(Object target, String name, Class<?>[] types, Object... args) throws Exception {
        return target.getClass().getMethod(name, types).invoke(target, args);
    }

    static void runShellCommand(String... arguments) throws Exception {
        // Binder rejects the protected log FD; give cmd pipes and copy its output ourselves.
        java.lang.Process command = new ProcessBuilder(arguments).redirectErrorStream(true).start();
        Thread output = new Thread(() -> {
            try { command.getInputStream().transferTo(System.out); }
            catch (java.io.IOException error) { System.err.println("Launcher output: " + error.getMessage()); }
        }, "gxr-pin-launch-output");
        output.setDaemon(true);
        try {
            command.getOutputStream().close();
            output.start();
            if (!command.waitFor(10, TimeUnit.SECONDS)) throw new IllegalStateException("App launch timed out");
            output.join(1000);
            if (command.exitValue() != 0) throw new IllegalStateException("App launch failed");
        } finally {
            command.destroyForcibly();
            command.getInputStream().close();
            command.getErrorStream().close();
        }
    }

    private static Object manager() throws Exception {
        return Class.forName("android.app.ActivityTaskManager").getMethod("getInstance").invoke(null);
    }
    @SuppressWarnings("unchecked")
    private static List<RunningTaskInfo> tasks() throws Exception {
        return (List<RunningTaskInfo>) invoke(manager(), "getTasks", new Class<?>[] {int.class}, 100);
    }
    private static int mode(RunningTaskInfo task) throws Exception {
        return task.getClass().getField("xrDesktopMode").getInt(task);
    }
    private static boolean marked(RunningTaskInfo task, String pkg) throws Exception {
        return task.getClass().getField("userId").getInt(task) == 0 && task.baseIntent != null &&
                task.baseIntent.hasCategory(MARKER) && task.baseActivity != null &&
                task.baseActivity.getPackageName().equals(pkg);
    }
    /** Preinstalled apps may pin; core processes and the controls needed for recovery may not. */
    static boolean allowedApplication(ApplicationInfo info, String pkg) {
        return info.uid >= 10000 && !pkg.equals("me.weishu.kernelsu") && !pkg.equals("com.android.systemui");
    }

    private static Intent launcher(String pkg) throws Exception {
        Object thread = Class.forName("android.app.ActivityThread").getMethod("systemMain").invoke(null);
        Context context = (Context) invoke(thread, "getSystemContext", new Class<?>[0]);
        ApplicationInfo info = context.getPackageManager().getApplicationInfo(pkg, 0);
        if (!allowedApplication(info, pkg)) {
            throw new IllegalArgumentException("Core system processes, SystemUI and KernelSU cannot be pinned");
        }
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(pkg);
        if (intent == null || intent.getComponent() == null) throw new IllegalArgumentException("No launcher activity");
        PackageManager packages = context.getPackageManager();
        ActivityInfo activity = packages.getActivityInfo(intent.getComponent(), 0);
        ordinaryActivity(packages, intent.getComponent(), activity);
        if (activity.targetActivity != null) {
            ComponentName target = new ComponentName(pkg, activity.targetActivity);
            ordinaryActivity(packages, target, packages.getActivityInfo(target, 0));
        }
        return intent;
    }
    private static void ordinaryActivity(PackageManager packages, ComponentName component,
            ActivityInfo activity) throws Exception {
        // AZJ2 evaluates this flag before the overlay allowlist; XR apps must keep their own mode.
        if ((activity.getClass().getField("privateFlags").getInt(activity) & 16) != 0) {
            throw new IllegalArgumentException("Choose a 2D app, not an immersive XR app");
        }
        String property = "android.window.PROPERTY_XR_ACTIVITY_START_MODE";
        PackageManager.Property mode = null;
        try { mode = packages.getProperty(property, component); }
        catch (PackageManager.NameNotFoundException absent) { /* Try the application property below. */ }
        if (mode == null) {
            try { mode = packages.getProperty(property, component.getPackageName()); }
            catch (PackageManager.NameNotFoundException absent) { /* Ordinary apps need no XR property. */ }
        }
        if (mode != null && mode.isString() && mode.getString() != null &&
                !mode.getString().equals("XR_ACTIVITY_START_MODE_UNDEFINED") &&
                !mode.getString().equals("XR_ACTIVITY_START_MODE_HOME_SPACE")) {
            throw new IllegalArgumentException("Choose an ordinary Home Space app");
        }
    }
    private static void reorder(RunningTaskInfo task, boolean top) throws Exception {
        Class<?> tokenType = Class.forName("android.window.WindowContainerToken");
        Class<?> transactionType = Class.forName("android.window.WindowContainerTransaction");
        Object token = task.getClass().getField("token").get(task);
        Object transaction = transactionType.getConstructor().newInstance();
        invoke(transaction, "reorder", new Class<?>[] {tokenType, boolean.class}, token, top);
        Object organizer = Class.forName("android.window.WindowOrganizer").getConstructor().newInstance();
        invoke(organizer, "applyTransaction", new Class<?>[] {transactionType}, transaction);
    }
    private static void close(RunningTaskInfo task) throws Exception {
        Object service = Class.forName("android.app.ActivityTaskManager").getMethod("getService").invoke(null);
        Method remove = Class.forName("android.app.IActivityTaskManager").getMethod("removeTask", int.class);
        if (!Boolean.TRUE.equals(remove.invoke(service, task.taskId))) throw new IllegalStateException("Could not close pinned task");
    }

    static void verifyMenuTask(PinRequest request, RunningTaskInfo task) throws Exception {
        if (task.taskId != request.taskId || mode(task) != 1 ||
                task.getClass().getField("userId").getInt(task) != 0 ||
                task.baseActivity == null || task.topActivity == null ||
                !task.baseActivity.getPackageName().equals(request.packageName) ||
                !task.topActivity.getPackageName().equals(request.packageName) ||
                !PinnedPanels.isTaskVisible(task)) {
            throw new IllegalStateException("The selected ordinary window changed; reopen its menu");
        }
    }

    static void requireNewWindow(List<RunningTaskInfo> current, String pkg, int closingTask) throws Exception {
        for (RunningTaskInfo task : current) {
            if (task.taskId == closingTask || task.getClass().getField("userId").getInt(task) != 0 ||
                    task.baseActivity == null || !task.baseActivity.getPackageName().equals(pkg)) continue;
            if (marked(task, pkg) && mode(task) == 4) continue;
            throw new IllegalStateException("Close this app's existing windows first, or use its Pin app menu and confirm Reopen and pin");
        }
    }

    @SuppressWarnings("deprecation") // Standalone app_process must initialise its own main Looper.
    public static void main(String[] args) {
        try {
            if (args.length == 1 && args[0].equals("check")) {
                Class<?> node = Class.forName("android.graphics.CPM$Node");
                Class<?> vec = Class.forName("android.graphics.CPM$Vec3");
                Class<?> receiver = Class.forName("android.graphics.CPM$HitTestResultReceiver");
                Class.forName("android.graphics.CPM").getMethod("hitTest", node, vec, vec, receiver, int.class);
                Class.forName("android.graphics.CPM").getMethod("notifySystemOverlayStateChanged", boolean.class);
                Class.forName("android.app.ActivityTaskManager").getMethod("getService");
                Class.forName("android.app.IActivityTaskManager").getMethod("setFocusedTask", int.class);
                Class<?> metadata = Class.forName("android.graphics.CPM$SysUIMetadata");
                Class<?> scrim = Class.forName("android.graphics.CPM$SysUIMetadata$ScrimConfig");
                Class.forName("android.graphics.CPM$NodeUpdates").getMethod("setSysUIMetadata", node, metadata);
                Object colour = vec.getConstructor(float.class, float.class, float.class).newInstance(0f, 0f, 0f);
                Object transparent = scrim.getConstructor(vec, float.class).newInstance(colour, 0f);
                Object panelMetadata = metadata.getConstructor().newInstance();
                metadata.getField("scrimConfig").set(panelMetadata, transparent);
                if (scrim.getField("targetAlpha").getFloat(transparent) != 0) {
                    throw new IllegalStateException("Panel scrim contract mismatch");
                }
                Class.forName("android.app.TaskInfo").getField("xrDesktopMode");
                Class.forName("android.app.TaskInfo").getField("userId");
                ActivityInfo.class.getField("privateFlags");
                Class<?> token = Class.forName("android.window.WindowContainerToken");
                Class<?> transaction = Class.forName("android.window.WindowContainerTransaction");
                transaction.getMethod("reorder", token, boolean.class);
                Class.forName("android.window.WindowOrganizer").getMethod("applyTransaction", transaction);
                if (!new Intent(Intent.ACTION_MAIN).addCategory(MARKER).cloneFilter().hasCategory(MARKER)) {
                    throw new IllegalStateException("Task marker does not survive Intent filtering");
                }
                RunningTaskInfo info = new RunningTaskInfo();
                info.getClass().getField("isVisible").setBoolean(info, true);
                info.getClass().getField("isVisibleRequested").setBoolean(info, true);
                if (!PinnedPanels.isTaskVisible(info)) throw new IllegalStateException("Visibility fields mismatch");
                info.taskId = 42;
                info.baseActivity = new ComponentName("app.valid", "app.valid.Main");
                info.getClass().getField("xrDesktopMode").setInt(info, 1);
                try {
                    requireNewWindow(Collections.singletonList(info), "app.valid", 0);
                    throw new AssertionError("An ordinary window would be reused");
                } catch (IllegalStateException expected) { /* Opening a normal task is rejected before launch. */ }
                requireNewWindow(Collections.singletonList(info), "app.valid", 42);
                info.baseIntent = new Intent(Intent.ACTION_MAIN).addCategory(MARKER);
                info.getClass().getField("xrDesktopMode").setInt(info, 4);
                requireNewWindow(Collections.singletonList(info), "app.valid", 0);
                if (Looper.myLooper() == null) Looper.prepareMainLooper();
                HandlerThread owner = new HandlerThread("gxr-pin-readonly-check");
                owner.start();
                try {
                    PinnedPanels panels = new PinnedPanels();
                    CheckOwner caption = new CheckOwner(new Handler(owner.getLooper()));
                    panels.bindCaptionOwner(caption);
                    panels.destroyCaption(caption, info);
                    panels.shutdown();
                    for (int attempt = 0; attempt < 100 && !panels.isRestored(); attempt++) Thread.sleep(10);
                    if (!panels.isRestored() || !caption.closed) throw new IllegalStateException("Owner-thread cleanup failed");
                } finally { owner.quitSafely(); owner.join(1000); }
                System.out.println("API_CHECK_OK - interfaces, panel scrim, marker, visibility fields and owner-thread cleanup; no device changes");
                return;
            }
            if (Process.myUid() != 0) throw new SecurityException("Root required");
            Looper.prepareMainLooper();
            if (args.length == 4 && args[0].equals("close-for-pin")) {
                PinRequest request = new PinRequest(Long.parseLong(args[3]), Integer.parseInt(args[1]), args[2]);
                request.requireFresh(SystemClock.uptimeMillis());
                launcher(request.packageName);
                List<RunningTaskInfo> current = tasks();
                requireNewWindow(current, request.packageName, request.taskId);
                for (RunningTaskInfo task : current) {
                    if (task.taskId != request.taskId) continue;
                    verifyMenuTask(request, task);
                    request.requireFresh(SystemClock.uptimeMillis());
                    close(task);
                    System.out.println("Closed the confirmed window for pinning");
                    return;
                }
                throw new IllegalStateException("The selected window is no longer open");
            }
            if (args.length == 1 && args[0].equals("close-all")) {
                int count = 0;
                for (RunningTaskInfo task : tasks()) {
                    if (task.baseActivity != null && marked(task, task.baseActivity.getPackageName()) && mode(task) == 4) {
                        close(task);
                        count++;
                    }
                }
                System.out.println("Closed " + count + " pinned windows; apps were not force-stopped");
                return;
            }
            if (args.length != 2 || !args[1].matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")) {
                throw new IllegalArgumentException("Expected action and installed app package");
            }
            String action = args[0], pkg = args[1];
            if (action.equals("preflight")) {
                launcher(pkg);
                requireNewWindow(tasks(), pkg, 0);
                return;
            }
            if (action.equals("resolve")) {
                System.out.println(launcher(pkg).getComponent().flattenToString());
                return;
            }
            if (action.equals("launch")) {
                requireNewWindow(tasks(), pkg, 0);
                for (RunningTaskInfo task : tasks()) {
                    if (marked(task, pkg) && mode(task) == 4) {
                        reorder(task, true);
                        System.out.println("Restored pinned window");
                        return;
                    }
                }
                Intent intent = launcher(pkg);
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
                Set<Integer> previous = new HashSet<>();
                for (RunningTaskInfo task : tasks()) previous.add(task.taskId);
                try {
                    // Use Android's shell launcher rather than attributing a root app_process to android.
                    runShellCommand("/system/bin/am", "start", "--user", "0",
                            "-a", Intent.ACTION_MAIN, "-c", Intent.CATEGORY_LAUNCHER,
                            "-n", intent.getComponent().flattenToString(), "-f", Integer.toString(intent.getFlags()),
                            "-c", MARKER);
                    for (int attempt = 0; attempt < 30; attempt++) {
                        for (RunningTaskInfo task : tasks()) if (marked(task, pkg) && mode(task) == 4) {
                            System.out.println("PINNED - native overlay task " + task.taskId);
                            return;
                        }
                        Thread.sleep(100);
                    }
                    throw new IllegalStateException("No overlay task appeared. Close the app's existing window, then retry Pin");
                } catch (Exception failure) {
                    for (RunningTaskInfo task : tasks()) {
                        if (!previous.contains(task.taskId) && marked(task, pkg)) close(task);
                    }
                    throw failure;
                }
            }
            JSONArray result = new JSONArray();
            for (RunningTaskInfo task : tasks()) {
                if (!marked(task, pkg) || mode(task) != 4) continue;
                if (action.equals("minimize")) reorder(task, false);
                else if (action.equals("restore")) reorder(task, true);
                else if (action.equals("close")) close(task);
                else if (!action.equals("status")) throw new IllegalArgumentException("Unknown action");
                JSONObject item = new JSONObject();
                item.put("id", task.taskId);
                item.put("visible", task.getClass().getField("isVisible").getBoolean(task));
                result.put(item);
            }
            System.out.println(new JSONObject().put("package", pkg).put("tasks", result));
        } catch (Exception value) {
            Throwable cause = value.getCause() == null ? value : value.getCause();
            System.err.println(cause.getClass().getSimpleName() + ": " + cause.getMessage());
            System.exit(1);
        }
    }
}
