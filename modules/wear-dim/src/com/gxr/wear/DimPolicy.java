package com.gxr.wear;

/** Only a confirmed, continuously worn no-eyes interval can request dimming. */
public final class DimPolicy {
    private long absentSince = -1;

    public boolean update(long now, boolean mounted, boolean interactive, int eyes) {
        if (!mounted || !interactive || eyes != 1) {
            absentSince = -1;
            return false;
        }
        if (absentSince < 0) absentSince = now;
        return now - absentSince >= 60000;
    }

    public static float dimLevel(float current) {
        if (!Float.isFinite(current) || current < 0 || current > 1) {
            throw new IllegalArgumentException("Invalid display brightness");
        }
        return current * 0.2f;
    }
}
