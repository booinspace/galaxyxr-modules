package com.gxr.mic;

/** Mixer ownership: restore only a value this session wrote, never another writer's value. */
public final class GainState {
    public int saved = -1;
    public int written = -1;

    public static boolean eligible(String pkg, int source, boolean silenced) {
        return !silenced && source == 10 && "virtualdesktop.android".equals(pkg);
    }

    public static boolean otherMic(int source) {
        return source != 8 && source != 1997 && source != 1998 && source != 1999;
    }

    public static boolean wanted(boolean vd, boolean other, int mode) {
        if (mode == 0) return vd || other;
        if (mode != 1 && mode != 2) throw new IllegalArgumentException("MODE must be 0, 1 or 2");
        return vd && (mode == 1 || !other);
    }

    public int target(boolean boost, int current, int gain) {
        if (current < 0 || current > 124 || gain < 0 || gain > 40) {
            throw new IllegalArgumentException("Invalid mixer value or GAIN_DB");
        }
        if (boost) return Math.min(124, (current == written && saved >= 0 ? saved : current) + gain);
        return current == written && saved >= 0 ? saved : current;
    }

    public void own(int before, int after) {
        if (before != written || saved < 0) saved = before;
        written = after;
    }
    public void clear() { saved = written = -1; }
}
