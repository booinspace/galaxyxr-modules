import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import local.gxr.audio.MixerEngine;

public final class MixerEngineTest {
    private static final class Player extends MixerEngine.Player {
        int applications;
        int clears;
        int percent = 100;
        boolean replacing;
        boolean failApply;
        boolean failClear;
        Player(int id, String key, boolean active, boolean supported) { super(id, key, key, active, supported); }
        @Override public void apply(int value, boolean replace) throws Exception {
            if (failApply) throw new Exception("player unavailable");
            applications++;
            percent = value;
            replacing = replace;
        }
        @Override public void clear() throws Exception {
            if (failClear) throw new Exception("temporarily unavailable");
            clears++;
            percent = 100;
        }
    }
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        MixerEngine mixer = new MixerEngine();
        Player music = new Player(1, "music", true, true);
        Player music2 = new Player(2, "music", true, true);
        Player vr = new Player(3, "vr", true, true);
        Player unsupported = new Player(4, "native", true, false);
        mixer.enable(true);
        mixer.update(Arrays.asList(music, music2, vr, unsupported));
        check(music.applications == 0 && mixer.ownedCount() == 0, "100% must leave stock untouched");
        mixer.set("music", 30);
        check(music.percent == 30 && music2.percent == 30 && vr.percent == 100, "all players of one app, not other apps");
        check(!music.replacing && mixer.ownedCount() == 2, "first application creates one envelope each");
        mixer.set("music", 30);
        check(music.applications == 1, "callbacks must not reapply unchanged gains");
        mixer.set("music", 20);
        check(music.percent == 20 && music.replacing, "slider replaces its own envelope");
        mixer.set("vr", 0);
        check(vr.percent == 0, "zero mutes only chosen app");
        mixer.update(Arrays.asList(music, music2, vr, unsupported));
        check(vr.percent == 0 && vr.clears == 0, "mute-status callbacks must not remove our mute");
        mixer.set("native", 0);
        check(unsupported.applications == 0, "unsupported players remain untouched");
        Player recreated = new Player(5, "music", true, true);
        mixer.update(Arrays.asList(recreated, vr, unsupported));
        check(recreated.percent == 20 && mixer.ownedCount() == 2, "saved levels follow replacement players");
        mixer.update(Arrays.asList(new Player(5, "music", false, true), vr, unsupported));
        check(recreated.clears == 1 && mixer.ownedCount() == 1, "paused player loses only our envelope");
        mixer.enable(false);
        check(vr.percent == 100 && mixer.ownedCount() == 0, "bypass restores owned effects");
        mixer.enable(true);
        check(vr.percent == 0, "reenable retains preferences");
        mixer.set("vr", 100);
        check(vr.percent == 100 && mixer.ownedCount() == 0, "100 removes rather than overwrites system volume");
        mixer.update(Arrays.asList(recreated, vr));
        check(recreated.percent == 20, "resumed player inherits app preference");
        mixer.reset();
        check(recreated.percent == 100 && mixer.level("music") == 100, "reset clears preferences and effects");
        recreated.failApply = true;
        mixer.set("music", 10);
        check(mixer.ownedCount() == 0 && mixer.failures().containsKey("music"), "failed write never records false ownership");
        recreated.failApply = false;
        mixer.update(Arrays.asList(recreated, vr));
        check(recreated.percent == 10 && mixer.failures().isEmpty(), "playback updates can recover a failed player");
        recreated.failClear = true;
        mixer.enable(false);
        check(mixer.ownedCount() == 1 && !mixer.failures().isEmpty(), "failed cleanup retains ownership for retry");
        recreated.failClear = false;
        mixer.enable(false);
        check(mixer.ownedCount() == 0, "cleanup can be retried");
        mixer.enable(true);
        recreated.failClear = true;
        mixer.update(Collections.emptyList());
        check(mixer.ownedCount() == 0, "released players must not block shutdown");
        Map<String, Integer> saved = new HashMap<>();
        saved.put("saved", 45);
        MixerEngine loaded = new MixerEngine();
        loaded.load(saved);
        check(loaded.level("saved") == 45, "persistent settings load");
        for (int invalid : new int[] {-1, 101, Integer.MAX_VALUE}) {
            try { mixer.set("vr", invalid); throw new AssertionError("invalid volume accepted"); }
            catch (IllegalArgumentException expected) { }
        }
        check(MixerEngine.eligible(10123, 1) && MixerEngine.eligible(110123, 14), "ordinary media/game across Android users");
        check(!MixerEngine.eligible(1000, 1) && !MixerEngine.eligible(99001, 1)
                && !MixerEngine.eligible(10123, 4) && !MixerEngine.eligible(10123, 2), "exclude system, isolated, alarms and calls");
        check(MixerEngine.playing(2) && !MixerEngine.playing(3) && !MixerEngine.playing(4)
                && !MixerEngine.playing(-1), "raw started state keeps muted playback eligible and excludes stopped players");
        System.out.println("PASS: per-app isolation, multi-player changes, lifecycle, bypass/reset, failures and ranges");
    }
}
