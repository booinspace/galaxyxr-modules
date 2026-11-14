package local.gxr.workspaces;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Standalone module entry point; native callbacks never wait for a JavaScript reply. */
public final class WorkspaceController {
    private final Context context;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ScheduledThreadPoolExecutor worker = new ScheduledThreadPoolExecutor(1);
    private final List<WorkspacePanel> panels = new ArrayList<>();
    private final File directory;
    private final String token;
    private final WorkspaceAndroidHost host;
    private final WorkspaceEngine engine;
    private volatile long heartbeat = SystemClock.uptimeMillis();
    private volatile boolean stopping, stopped, working;
    private volatile java.util.concurrent.Future<?> operation;
    private volatile String status = "Preparing saved workspaces…";
    private long previewSequence;
    private final Runnable watchdog = new Runnable() {
        @Override public void run() {
            if (stopping) return;
            if (!live()) { stop(); return; }
            main.postDelayed(this, 500);
        }
    };
    public WorkspaceController(Context context, Object bridge, String token) throws Exception {
        if (!token.matches("[0-9a-f]{32}")) throw new IllegalArgumentException("Invalid workspace session");
        this.context = context; this.token = token;
        directory = new File(context.getFilesDir(), "booinspace-workspaces");
        if (!directory.isDirectory() && !directory.mkdirs()) throw new java.io.IOException("Cannot create private workspace storage");
        if (java.nio.file.Files.isSymbolicLink(directory.toPath())) throw new SecurityException("Invalid workspace directory");
        directory.setReadable(false, false); directory.setWritable(false, false); directory.setExecutable(false, false);
        directory.setReadable(true, true); directory.setWritable(true, true); directory.setExecutable(true, true);
        host = new WorkspaceAndroidHost(context, bridge, directory, token, this::live, this::report);
        engine = new WorkspaceEngine(new WorkspaceStore(directory), host);
        worker.setRemoveOnCancelPolicy(true);
        worker.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
        main.post(watchdog);
        run(() -> {
            engine.adoptInitialScene();
            report(engine.bound() ? "Desk contains your current windows" : "Choose a workspace to restore. Current windows are saved before switching.");
        });
        worker.scheduleWithFixedDelay(() -> {
            if (!live() || working || !engine.bound()) return;
            try { engine.autosave(); }
            catch (Exception error) { report("Layout not saved: " + message(error)); }
        }, 10, 10, TimeUnit.SECONDS);
        Log.i("GxrWorkspaces", "WORKSPACES_READY private native Recents strip");
    }
    public void pulse() { heartbeat = SystemClock.uptimeMillis(); }
    private boolean live() { return !stopping && SystemClock.uptimeMillis() - heartbeat < 5000; }
    private static String message(Throwable error) { return error.getMessage() == null ? error.toString() : error.getMessage(); }
    interface Work { void run() throws Exception; }
    private void run(Work work) {
        if (stopping || working) return;
        working = true; refresh();
        operation = worker.submit(() -> {
            try { if (!live()) throw new IllegalStateException("Workspace service stopped"); work.run(); }
            catch (Exception error) { Log.w("GxrWorkspaces", "WORKSPACE_OPERATION_FAILED", error); report(error instanceof InterruptedException ? "Opening paused; apps stay open. Choose a workspace to continue." : message(error)); }
            finally { working = false; refresh(); }
        });
    }
    void stopWaiting() {
        java.util.concurrent.Future<?> current = operation;
        if (engine.busy() && current != null) current.cancel(true);
    }
    void report(String value) {
        status = value;
        try { WorkspaceFiles.write(new File(directory, "frontend.txt"), (token + "\n" + status()).getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
        catch (Exception error) { Log.w("GxrWorkspaces", "STATUS_WRITE_FAILED", error); }
        refresh();
    }
    void detach(WorkspacePanel panel) { main.post(() -> { panel.close(); panels.remove(panel); }); }
    void refresh() { main.post(() -> { for (WorkspacePanel panel : new ArrayList<>(panels)) panel.refresh(); }); }
    WorkspaceStore.Index index() { return engine.index(); }
    boolean busy() { return working || engine.busy(); }
    boolean bound() { return engine.bound(); }
    String text() { return status; }
    File preview(String id) {
        if (!id.matches("[0-9a-f-]{36}")) throw new IllegalArgumentException("Invalid workspace ID");
        return new File(directory, "preview-" + id + ".jpg");
    }
    void acknowledge() { run(engine::acknowledge); }
    void saveCurrent() { run(() -> { if (!engine.bound()) throw new IllegalStateException("Choose a workspace first; saved layouts have not been overwritten"); engine.autosave(); report("Layout saved"); }); }
    void select(Workspace workspace, Object element) {
        run(() -> {
            if (!engine.index().acknowledged) throw new IllegalStateException("Confirm setup before switching");
            // Leave the stock switcher before resizing windows or launching an immersive app.
            AndroidAccess.on(main, () -> {
                Object provider = AndroidAccess.get(element, "getOverviewViewModel");
                AndroidAccess.get(AndroidAccess.get(provider, "get"), "hideOverview"); return null;
            });
            Thread.sleep(250);
            engine.switchTo(workspace.id);
            captureLater(workspace.id);
        });
    }
    void create(String name, Object element) {
        run(() -> {
            WorkspaceStore.Index old = engine.index();
            if (old.workspaces.size() >= Workspace.MAX_WORKSPACES) throw new IllegalStateException("Maximum eight workspaces");
            Workspace added = Workspace.empty(name);
            List<Workspace> next = new ArrayList<>(old.workspaces); next.add(added);
            engine.edit(new WorkspaceStore.Index(next, old.active, old.pending, old.acknowledged));
            report("Created " + added.name + ". Select it to start with an empty scene.");
        });
    }
    void rename(String id, String name) { run(() -> {
        Workspace old = engine.index().get(id);
        engine.edit(engine.index().replace(new Workspace(old.id, name, old.lastUsed, old.windows))); report("Workspace renamed");
    }); }
    void remove(String id) { run(() -> {
        WorkspaceStore.Index old = engine.index();
        if (old.active.equals(id) || old.pending.equals(id)) throw new IllegalStateException("Switch to another workspace before deleting this one");
        List<Workspace> next = new ArrayList<>(old.workspaces); next.removeIf(w -> w.id.equals(id));
        engine.edit(new WorkspaceStore.Index(next, old.active, old.pending, old.acknowledged));
        java.nio.file.Files.deleteIfExists(preview(id).toPath()); report("Workspace deleted");
    }); }
    public void attachOverview(Object element) {
        main.post(() -> {
            if (!live()) return;
            try {
                for (WorkspacePanel panel : panels) if (panel.element == element) { panel.refresh(); return; }
                panels.removeIf(panel -> { if (panel.attached()) return false; panel.close(); return true; });
                if (panels.size() >= 3) throw new IllegalStateException("Too many Recents views");
                WorkspacePanel panel = new WorkspacePanel(context, element, this); panels.add(panel);
                if (engine.bound() && !busy()) run(() -> { engine.autosave(); report("Saved " + engine.index().get(engine.index().active).name); });
            } catch (Exception error) { Log.w("GxrWorkspaces", "RECENTS_ATTACH_FAILED", error); report("Recents: " + message(error)); }
        });
    }
    private void captureLater(String id) {
        long request = ++previewSequence;
        worker.schedule(() -> {
            if (!live() || request != previewSequence || !engine.index().pending.isEmpty() || !id.equals(engine.index().active)) return;
            try {
                // Match AZJ2's native screenshot path; never request secure layers.
                Class<?> capture = Class.forName("android.window.ScreenCapture");
                Class<?> argsType = Class.forName("android.window.ScreenCapture$CaptureArgs");
                Class<?> listenerType = Class.forName("android.window.ScreenCapture$ScreenCaptureListener");
                Object builder = Class.forName("android.window.ScreenCapture$CaptureArgs$Builder").getConstructor().newInstance();
                AndroidAccess.call(builder, "setSourceCrop", new Class<?>[]{Rect.class}, (Object)null);
                Object args = AndroidAccess.get(builder, "build");
                Object listener = capture.getMethod("createSyncCaptureListener").invoke(null);
                Object windowManager = AndroidAccess.staticCall("android.view.WindowManagerGlobal", "getWindowManagerService", new Class<?>[0]);
                Method method = Class.forName("android.view.IWindowManager").getMethod("captureDisplay", int.class, argsType, listenerType);
                AndroidAccess.invoke(method, windowManager, 0, args, listener);
                Object buffer = AndroidAccess.get(listener, "getBuffer");
                if (buffer == null) throw new IllegalStateException("Screenshot unavailable");
                Bitmap source = (Bitmap)AndroidAccess.get(buffer, "asBitmap");
                if (source == null) throw new IllegalStateException("Screenshot unavailable");
                Bitmap bitmap = Bitmap.createScaledBitmap(source, 360, Math.max(1, source.getHeight() * 360 / source.getWidth()), true);
                try {
                    ByteArrayOutputStream data = new ByteArrayOutputStream();
                    if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 80, data)) throw new java.io.IOException("Could not encode preview");
                    if (data.size() > 512 * 1024) throw new java.io.IOException("Preview too large");
                    WorkspaceFiles.write(preview(id), data.toByteArray());
                } finally { if (bitmap != source) bitmap.recycle(); source.recycle(); }
                refresh();
            } catch (Exception error) { Log.w("GxrWorkspaces", "PREVIEW_UNAVAILABLE", error); }
        }, 1500, TimeUnit.MILLISECONDS);
    }
    public String status() { return (stopped ? "STOPPED " : stopping ? "STOPPING " : "RUNNING ") + status; }
    public void stop() {
        synchronized (this) { if (stopping) return; stopping = true; }
        main.removeCallbacks(watchdog);
        main.post(() -> { for (WorkspacePanel panel : panels) panel.close(); panels.clear(); });
        worker.shutdownNow();
        Thread cleanup = new Thread(() -> {
            try { while (!worker.awaitTermination(1, TimeUnit.SECONDS)) { /* Leave the hook loaded until callbacks finish. */ } host.close(); stopped = true; report("STOPPED; current app windows were left open"); }
            catch (Exception error) { Log.e("GxrWorkspaces", "WORKSPACES_CLEANUP_PENDING", error); }
        }, "workspace-cleanup");
        cleanup.setDaemon(true); cleanup.start();
    }
    public boolean isStopped() { return stopped; }
}
