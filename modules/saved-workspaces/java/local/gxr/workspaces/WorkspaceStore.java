package local.gxr.workspaces;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;

/** Bounded, checksummed local storage; a failed write never replaces the last saved layout. */
public final class WorkspaceStore {
    private static final int MAGIC = 0x47585257, VERSION = 1, MAX_BYTES = 256 * 1024;
    public static final class Index {
        public final List<Workspace> workspaces;
        public final String active, pending;
        public final boolean acknowledged;
        public Index(List<Workspace> workspaces, String active, String pending, boolean acknowledged) {
            if (workspaces == null || workspaces.isEmpty() || workspaces.size() > Workspace.MAX_WORKSPACES) throw new IllegalArgumentException("Invalid workspace count");
            HashSet<String> ids = new HashSet<>();
            for (Workspace w : workspaces) if (w == null || !ids.add(w.id)) throw new IllegalArgumentException("Duplicate workspace");
            if (!ids.contains(active) || (!pending.isEmpty() && !ids.contains(pending))) throw new IllegalArgumentException("Invalid active workspace");
            this.workspaces = java.util.Collections.unmodifiableList(new ArrayList<>(workspaces));
            this.active = active;
            this.pending = pending;
            this.acknowledged = acknowledged;
        }
        public Workspace get(String id) {
            for (Workspace w : workspaces) if (w.id.equals(id)) return w;
            throw new IllegalArgumentException("Workspace no longer exists");
        }
        public Index replace(Workspace updated) {
            List<Workspace> next = new ArrayList<>(workspaces);
            for (int i = 0; i < next.size(); i++) if (next.get(i).id.equals(updated.id)) {
                next.set(i, updated); return new Index(next, active, pending, acknowledged);
            }
            throw new IllegalArgumentException("Workspace no longer exists");
        }
        public Index switching(String target) { return new Index(workspaces, active, target, acknowledged); }
        public Index selected(String id) { return new Index(workspaces, id, "", acknowledged); }
    }
    private final File file;
    public WorkspaceStore(File directory) throws IOException { this(directory, "layouts.gxrw"); }
    private WorkspaceStore(File directory, String name) throws IOException {
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Cannot create private workspace storage");
        if (Files.isSymbolicLink(directory.toPath())) throw new IOException("Invalid workspace storage");
        file = new File(directory, name);
    }
    public synchronized Index read() throws IOException {
        if (!file.exists()) {
            List<Workspace> initial = Arrays.asList(Workspace.empty("Cinema"), Workspace.empty("Desk"), Workspace.empty("VRChat"));
            return new Index(initial, initial.get(1).id, "", false);
        }
        if (Files.isSymbolicLink(file.toPath()) || file.length() > MAX_BYTES || file.length() < 44) throw new IOException("Invalid workspace file; saved data was preserved");
        try {
            byte[] bytes = Files.readAllBytes(file.toPath());
            DataInputStream in = new DataInputStream(new ByteArrayInputStream(bytes));
            if (in.readInt() != MAGIC || in.readInt() != VERSION) throw new IOException("Unsupported workspace format");
            int length = in.readInt();
            if (length != bytes.length - 44) throw new IOException("Truncated workspace file");
            byte[] expected = new byte[32], payload = new byte[length];
            in.readFully(expected); in.readFully(payload);
            if (!MessageDigest.isEqual(expected, digest(payload))) throw new IOException("Workspace checksum failed; saved data was preserved");
            DataInputStream data = new DataInputStream(new ByteArrayInputStream(payload));
            String active = data.readUTF(), pending = data.readUTF();
            boolean acknowledged = data.readBoolean();
            int count = bounded(data.readInt(), 1, Workspace.MAX_WORKSPACES);
            List<Workspace> workspaces = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                String id = data.readUTF(), name = data.readUTF();
                long used = data.readLong();
                int windows = bounded(data.readInt(), 0, Workspace.MAX_WINDOWS);
                List<Workspace.Window> items = new ArrayList<>();
                for (int j = 0; j < windows; j++) {
                    String component = data.readUTF();
                    int kind = data.readInt(), width = data.readInt(), height = data.readInt();
                    boolean minimized = data.readBoolean();
                    float curve = data.readFloat();
                    float[] placement = floats(data, 16), rotation = floats(data, 4);
                    items.add(new Workspace.Window(component, kind, width, height, minimized, placement, rotation, curve));
                }
                workspaces.add(new Workspace(id, name, used, items));
            }
            if (data.available() != 0) throw new IOException("Trailing workspace data");
            return new Index(workspaces, active, pending, acknowledged);
        } catch (IllegalArgumentException invalid) { throw new IOException("Invalid saved layout; data was preserved", invalid); }
    }
    public synchronized void save(Index index) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(buffer);
        out.writeUTF(index.active); out.writeUTF(index.pending); out.writeBoolean(index.acknowledged);
        out.writeInt(index.workspaces.size());
        for (Workspace w : index.workspaces) {
            out.writeUTF(w.id); out.writeUTF(w.name); out.writeLong(w.lastUsed); out.writeInt(w.windows.size());
            for (Workspace.Window state : w.windows) {
                // Revalidate public arrays immediately before crossing the persistence boundary.
                Workspace.Window item = new Workspace.Window(state.component, state.kind, state.width, state.height,
                        state.minimized, state.placement, state.rotation, state.curvature);
                out.writeUTF(item.component); out.writeInt(item.kind); out.writeInt(item.width); out.writeInt(item.height);
                out.writeBoolean(item.minimized); out.writeFloat(item.curvature);
                for (float v : item.placement) out.writeFloat(v);
                for (float v : item.rotation) out.writeFloat(v);
            }
        }
        out.flush(); byte[] payload = buffer.toByteArray();
        if (payload.length + 44 > MAX_BYTES) throw new IOException("Workspace data is too large");
        File temporary = new File(file.getParentFile(), file.getName() + ".new");
        if (Files.isSymbolicLink(temporary.toPath()) || Files.isSymbolicLink(file.toPath())) throw new IOException("Invalid workspace file");
        try {
            try (FileOutputStream stream = new FileOutputStream(temporary); DataOutputStream data = new DataOutputStream(stream)) {
                data.writeInt(MAGIC); data.writeInt(VERSION); data.writeInt(payload.length); data.write(digest(payload)); data.write(payload);
                data.flush(); stream.getFD().sync();
            }
            Files.move(temporary.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(temporary.toPath()); }
    }
    public void saveRecovery(Workspace workspace) throws IOException {
        new WorkspaceStore(file.getParentFile(), "recovery.gxrw").save(
                new Index(java.util.Collections.singletonList(workspace), workspace.id, "", true));
    }
    public Workspace readRecovery() throws IOException {
        WorkspaceStore recovery = new WorkspaceStore(file.getParentFile(), "recovery.gxrw");
        if (!recovery.exists()) throw new IOException("Recovery layout is missing");
        Index index = recovery.read();
        return index.get(index.active);
    }
    public boolean exists() { return file.exists(); }
    public boolean followEnabled() throws IOException {
        File preference = new File(file.getParentFile(), "follow");
        if (!Files.exists(preference.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) return false;
        if (!Files.isRegularFile(preference.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS) || preference.length() != 1) throw new IOException("Invalid Follow me preference");
        try (java.io.InputStream in = Files.newInputStream(preference.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            int value = in.read();
            if ((value != 0 && value != 1) || in.read() != -1) throw new IOException("Invalid Follow me preference");
            return value == 1;
        }
    }
    public void setFollowEnabled(boolean enabled) throws IOException {
        File preference = new File(file.getParentFile(), "follow"), temporary = new File(file.getParentFile(), "follow.new");
        if (Files.isSymbolicLink(preference.toPath()) || Files.isSymbolicLink(temporary.toPath())) throw new IOException("Invalid Follow me preference");
        try {
            try (FileOutputStream out = new FileOutputStream(temporary)) { out.write(enabled ? 1 : 0); out.getFD().sync(); }
            Files.move(temporary.toPath(), preference.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(temporary.toPath()); }
    }
    private static int bounded(int value, int min, int max) throws IOException {
        if (value < min || value > max) throw new IOException("Invalid workspace item count");
        return value;
    }
    private static float[] floats(DataInputStream in, int count) throws IOException {
        float[] out = new float[count]; for (int i = 0; i < count; i++) out[i] = in.readFloat(); return out;
    }
    private static byte[] digest(byte[] bytes) throws IOException {
        try { return MessageDigest.getInstance("SHA-256").digest(bytes); }
        catch (java.security.NoSuchAlgorithmException impossible) { throw new IOException(impossible); }
    }
}
