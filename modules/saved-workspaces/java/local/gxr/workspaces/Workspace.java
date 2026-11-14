package local.gxr.workspaces;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;

/** Validated app layouts; no documents, credentials or arbitrary launch intents are saved. */
public final class Workspace {
    public static final int MAX_WORKSPACES = 8;
    public static final int MAX_WINDOWS = 16;
    public final String id;
    public final String name;
    public final long lastUsed;
    public final List<Window> windows;

    public Workspace(String id, String name, long lastUsed, List<Window> windows) {
        if (id == null || !id.matches("[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}")) throw new IllegalArgumentException("Invalid workspace ID");
        if (name == null || name.trim().isEmpty() || name.length() > 40 || name.chars().anyMatch(Character::isISOControl)) {
            throw new IllegalArgumentException("Use a name of 1–40 characters");
        }
        if (lastUsed < 0 || windows == null || windows.size() > MAX_WINDOWS) throw new IllegalArgumentException("Invalid workspace size");
        HashSet<String> apps = new HashSet<>();
        for (Window window : windows) {
            if (window == null || !apps.add(window.component)) {
                throw new IllegalArgumentException("Save one window per app activity; close duplicate windows first");
            }
        }
        this.id = id;
        this.name = name.trim();
        this.lastUsed = lastUsed;
        this.windows = Collections.unmodifiableList(new ArrayList<>(windows));
    }

    public static Workspace empty(String name) {
        return new Workspace(UUID.randomUUID().toString(), name, 0, Collections.emptyList());
    }
    public Workspace withWindows(List<Window> windows) { return new Workspace(id, name, System.currentTimeMillis(), windows); }
    public Workspace renamed(String name) { return new Workspace(id, name, lastUsed, windows); }

    public static final class Window {
        public static final int HOME = 0, PIN = 1, IMMERSIVE = 2;
        public final String component;
        public final int kind, width, height;
        public final boolean minimized;
        public final float[] placement, rotation;
        public final float curvature;
        public Window(String component, int kind, int width, int height, boolean minimized,
                float[] placement, float[] rotation, float curvature) {
            if (component == null || component.length() > 400 || !component.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+/[A-Za-z_$][A-Za-z0-9_.$]*")) {
                throw new IllegalArgumentException("Invalid app component");
            }
            if (kind < HOME || kind > IMMERSIVE || width < 64 || width > 16384 || height < 64 || height > 16384) {
                throw new IllegalArgumentException("Invalid app layout");
            }
            if (!Float.isFinite(curvature) || curvature < 0 || curvature > 1 || rotation == null || rotation.length != 4) {
                throw new IllegalArgumentException("Invalid app appearance");
            }
            double norm = 0;
            for (float v : rotation) { if (!Float.isFinite(v)) throw new IllegalArgumentException("Invalid rotation"); norm += v * v; }
            if (norm < .8 || norm > 1.2) throw new IllegalArgumentException("Invalid rotation norm");
            this.component = component;
            this.kind = kind;
            this.width = width;
            this.height = height;
            this.minimized = minimized;
            this.placement = WorkspaceMath.checked(placement);
            this.rotation = rotation.clone();
            for (int i = 0; i < 4; i++) this.rotation[i] /= Math.sqrt(norm);
            this.curvature = curvature;
        }
        public String packageName() { return component.substring(0, component.indexOf('/')); }
    }
}
