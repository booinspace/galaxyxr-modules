package com.gxr.wear;

/** Only a confirmed, continuously worn no-eyes interval can blank the panel. */
public final class DimPolicy {
    private long absentSince = -1;
    private int eyes = 2;

    public boolean update(long now, boolean mounted, boolean interactive, int observedEyes, boolean fresh) {
        if (!mounted || !interactive) {
            eyes = 2;
        } else if (fresh) {
            eyes = observedEyes;
        }
        // CPM publishes changes; no new snapshot does not mean tracking was lost.
        if (eyes != 1) {
            absentSince = -1;
            return false;
        }
        if (absentSince < 0) absentSince = now;
        return now - absentSince >= 60000;
    }
}
