package local.gxr.workspaces;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Keep shared app windows alive; only close/relaunch windows absent or changing overlay mode. */
public final class WorkspacePlan {
    public final List<Workspace.Window> close, launch, keep;
    public final Set<String> pausePackages;
    public WorkspacePlan(List<Workspace.Window> current, List<Workspace.Window> destination) {
        Map<String, Workspace.Window> old = index(current), next = index(destination);
        List<Workspace.Window> close = new ArrayList<>(), launch = new ArrayList<>(), keep = new ArrayList<>();
        Set<String> pause = new HashSet<>(), incomingPackages = new HashSet<>();
        for (Workspace.Window item : destination) incomingPackages.add(item.packageName());
        for (Workspace.Window item : current) {
            Workspace.Window target = next.get(item.component);
            if (!reusable(item, target)) close.add(item);
            if (!incomingPackages.contains(item.packageName())) pause.add(item.packageName());
        }
        // Immersive apps open last so their input/brightness state is established after the pins.
        for (Workspace.Window item : destination) {
            Workspace.Window previous = old.get(item.component);
            if (reusable(previous, item)) keep.add(item); else if (item.kind != Workspace.Window.IMMERSIVE) launch.add(item);
        }
        for (Workspace.Window item : destination) {
            Workspace.Window previous = old.get(item.component);
            if (!reusable(previous, item) && item.kind == Workspace.Window.IMMERSIVE) launch.add(item);
        }
        this.close = Collections.unmodifiableList(close);
        this.launch = Collections.unmodifiableList(launch);
        this.keep = Collections.unmodifiableList(keep);
        this.pausePackages = Collections.unmodifiableSet(pause);
    }
    private static boolean reusable(Workspace.Window current, Workspace.Window target) {
        return current != null && target != null && (current.kind == target.kind
                || (current.kind == Workspace.Window.HOME && target.kind == Workspace.Window.IMMERSIVE));
    }
    private static Map<String, Workspace.Window> index(List<Workspace.Window> windows) {
        if (windows == null || windows.size() > Workspace.MAX_WINDOWS) throw new IllegalArgumentException("Too many app windows");
        Map<String, Workspace.Window> map = new HashMap<>();
        for (Workspace.Window item : windows) if (item == null || map.put(item.component, item) != null) throw new IllegalArgumentException("Duplicate app activity");
        return map;
    }
}
