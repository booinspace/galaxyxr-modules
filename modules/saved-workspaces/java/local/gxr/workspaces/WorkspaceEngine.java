package local.gxr.workspaces;

import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/** Save before changing windows; retain an interrupted-switch marker until recovery succeeds. */
public final class WorkspaceEngine {
    public interface Host {
        void check() throws Exception;
        float[] anchor() throws Exception;
        List<Workspace.Window> capture(float[] anchor) throws Exception;
        void preflight(Workspace.Window window) throws Exception;
        void pause(Set<String> packages) throws Exception;
        void close(Workspace.Window window) throws Exception;
        void launch(Workspace.Window window) throws Exception;
        void restore(Workspace.Window window, float[] worldPlacement) throws Exception;
        void progress(String value);
        default void beginRestore() throws Exception {}
        default void foreground(Workspace.Window window) throws Exception {}
        default void awaitReady(Workspace.Window window) throws Exception {}
    }
    private final WorkspaceStore store;
    private final Host host;
    private final AtomicBoolean busy = new AtomicBoolean();
    private volatile WorkspaceStore.Index index;
    private float[] currentAnchor;
    private volatile boolean bound;
    public WorkspaceEngine(WorkspaceStore store, Host host) throws Exception {
        this.store = store; this.host = host; index = store.read();
    }
    public WorkspaceStore.Index index() { return index; }
    public boolean busy() { return busy.get(); }
    public boolean bound() { return bound; }
    public float[] placementAnchor() {
        if (!bound) throw new IllegalStateException("Open a workspace before following it");
        return WorkspaceMath.checked(currentAnchor);
    }
    public void updatePlacementAnchor(float[] placement) {
        if (!bound || busy()) throw new IllegalStateException("Cannot move an unfinished workspace");
        currentAnchor = WorkspaceMath.checked(placement);
    }
    public void acknowledge() throws Exception {
        WorkspaceStore.Index previous = index;
        WorkspaceStore.Index next = new WorkspaceStore.Index(previous.workspaces, previous.active, previous.pending, true);
        store.save(next); index = next;
    }
    public void adoptInitialScene() throws Exception {
        if (store.exists()) return;
        currentAnchor = host.anchor();
        Workspace current = index.get(index.active).withWindows(host.capture(currentAnchor));
        WorkspaceStore.Index next = index.replace(current);
        store.save(next); index = next; bound = true;
    }
    public void edit(WorkspaceStore.Index next) throws Exception {
        if (busy()) throw new IllegalStateException("Wait for the workspace switch to finish");
        store.save(next); index = next;
    }
    public void autosave() throws Exception {
        if (!bound || busy() || !index.pending.isEmpty()) return;
        host.check();
        WorkspaceStore.Index next = index.replace(index.get(index.active).withWindows(host.capture(currentAnchor)));
        store.save(next); index = next;
    }
    public void switchTo(String id) throws Exception {
        if (!busy.compareAndSet(false, true)) throw new IllegalStateException("A workspace is already opening");
        WorkspaceStore.Index before = index;
        float[] outgoingAnchor = currentAnchor;
        boolean changing = false;
        try {
            host.check();
            if (!before.acknowledged) throw new IllegalStateException("Confirm the workspace setup message first");
            Workspace target = before.get(id);
            if (bound && id.equals(before.active) && before.pending.isEmpty()) { autosaveWhileBusy(); return; }
            host.progress("Saving current workspace…");
            if (outgoingAnchor == null) outgoingAnchor = host.anchor();
            List<Workspace.Window> current = host.capture(outgoingAnchor);
            Workspace previous = before.get(before.active);
            // A restarted runtime must not overwrite a saved preset with Android's partially restored scene.
            if (bound) before = before.replace(previous.withWindows(current));
            else {
                store.saveRecovery(new Workspace(previous.id, "Before last switch", System.currentTimeMillis(), current));
            }
            for (Workspace.Window window : target.windows) { host.check(); host.preflight(window); }
            float[] incomingAnchor = host.anchor();
            WorkspaceStore.Index pending = before.switching(id);
            store.save(pending); index = pending;
            changing = true;
            apply(current, target.windows, incomingAnchor);
            WorkspaceStore.Index complete = before.replace(new Workspace(target.id, target.name, System.currentTimeMillis(), target.windows)).selected(id);
            store.save(complete); index = complete; currentAnchor = incomingAnchor; bound = true;
            host.progress("Opened " + target.name);
        } catch (Exception failure) {
            if (changing) {
                // A launched app may still be starting. Keep it open and let the user choose what happens next.
                bound = false;
                host.progress("Opening " + index.get(index.pending).name + " needs attention; opened apps were kept");
            }
            throw failure;
        } finally { busy.set(false); }
    }
    private void autosaveWhileBusy() throws Exception {
        host.check();
        WorkspaceStore.Index next = index.replace(index.get(index.active).withWindows(host.capture(currentAnchor)));
        store.save(next); index = next;
    }
    private void apply(List<Workspace.Window> current, List<Workspace.Window> target, float[] anchor) throws Exception {
        WorkspacePlan plan = new WorkspacePlan(current, target);
        host.check(); host.pause(plan.pausePackages);
        host.beginRestore();
        for (Workspace.Window window : plan.close) { host.check(); host.progress("Closing " + window.packageName()); host.close(window); }
        for (Workspace.Window window : plan.launch) if (window.kind != Workspace.Window.IMMERSIVE) {
            host.check(); host.progress("Opening " + window.packageName()); host.launch(window);
        }
        for (Workspace.Window window : target) {
            host.check();
            if (window.kind != Workspace.Window.IMMERSIVE) host.restore(window, WorkspaceMath.restore(anchor, window.placement));
        }
        for (Workspace.Window window : target) if (window.kind == Workspace.Window.IMMERSIVE) {
            host.check(); host.progress("Opening " + window.packageName());
            if (plan.launch.contains(window)) host.launch(window); else host.foreground(window);
        }
        for (Workspace.Window window : target) {
            host.check(); host.progress("Waiting for " + window.packageName() + " to open…"); host.awaitReady(window);
        }
    }
}
