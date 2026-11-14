package local.gxr.audio;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Owns one attenuation envelope per media player, leaving stream and app volume intact. */
public final class MixerEngine {
    public abstract static class Player {
        public final int id;
        public final String key;
        public final String label;
        public final boolean active;
        public final boolean supported;

        protected Player(int id, String key, String label, boolean active, boolean supported) {
            this.id = id;
            this.key = key;
            this.label = label;
            this.active = active;
            this.supported = supported;
        }

        public abstract void apply(int percent, boolean replace) throws Exception;
        public abstract void clear() throws Exception;
    }

    private static final class Owned {
        Player player;
        final int percent;
        Owned(Player player, int percent) { this.player = player; this.percent = percent; }
    }

    private final Map<Integer, Owned> owned = new HashMap<>();
    private List<Player> players = new ArrayList<>();
    private final Map<String, Integer> levels = new HashMap<>();
    private final Map<String, String> failures = new LinkedHashMap<>();
    private boolean enabled;

    public static int checkedPercent(int percent) {
        if (percent < 0 || percent > 100) throw new IllegalArgumentException("Volume must be 0–100%");
        return percent;
    }

    public static boolean eligible(int uid, int usage) {
        int appId = uid % 100000;
        return uid >= 0 && appId >= 10000 && appId < 20000 && (usage == 1 || usage == 14);
    }

    /** AZJ2 isActive() excludes muted players; their started state must retain our envelope. */
    public static boolean playing(int state) { return state == 2; }

    public void load(Map<String, Integer> saved) {
        for (Map.Entry<String, Integer> entry : saved.entrySet()) {
            levels.put(entry.getKey(), checkedPercent(entry.getValue()));
        }
    }

    public int level(String key) { return levels.containsKey(key) ? levels.get(key) : 100; }
    public boolean enabled() { return enabled; }
    public int ownedCount() { return owned.size(); }
    public Map<String, String> failures() { return new LinkedHashMap<>(failures); }

    public List<Player> players() { return new ArrayList<>(players); }

    public void update(List<Player> current) {
        players = new ArrayList<>(current);
        reconcile();
    }

    public void enable(boolean value) { enabled = value; reconcile(); }

    public void set(String key, int percent) {
        checkedPercent(percent);
        if (percent == 100) levels.remove(key); else levels.put(key, percent);
        reconcile();
    }

    public void reset() { levels.clear(); reconcile(); }

    private void reconcile() {
        Map<Integer, Player> current = new HashMap<>();
        for (Player player : players) current.put(player.id, player);
        failures.clear();
        for (Owned previous : new ArrayList<>(owned.values())) {
            Player next = current.get(previous.player.id);
            if (next == null) {
                // Privileged configurations include paused players; absence means release.
                owned.remove(previous.player.id);
                continue;
            }
            if (!next.key.equals(previous.player.key) || !next.active
                    || !next.supported || !enabled || level(next.key) == 100) {
                try {
                    previous.player.clear();
                    owned.remove(previous.player.id);
                } catch (Exception failure) {
                    failures.put(previous.player.key, "Could not remove attenuation; close and reopen this app's audio");
                }
            } else {
                previous.player = next;
            }
        }
        if (!enabled) return;
        for (Player player : players) {
            if (!player.active || !player.supported) continue;
            int percent = level(player.key);
            if (percent == 100) continue;
            Owned previous = owned.get(player.id);
            if (previous != null && previous.percent == percent) continue;
            try {
                player.apply(percent, previous != null);
                owned.put(player.id, new Owned(player, percent));
            } catch (Exception failure) {
                failures.put(player.key, "Player volume unavailable");
            }
        }
    }
}
