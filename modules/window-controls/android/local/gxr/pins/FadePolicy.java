package local.gxr.pins;

/** Eye-only fading; tracking loss and supervisor expiry restore full opacity. */
public final class FadePolicy {
    public static final float RESTING_ALPHA = 0.18f;
    private long lastLook = -1;
    private long lastStep = -1;
    private float alpha = 1;
    private boolean wasPinching;
    private boolean grabbed;

    public float update(long now, boolean fresh, boolean looking, boolean active, boolean pinching) {
        if (!active || !fresh || now < 0 || (lastStep >= 0 && now < lastStep)) {
            lastLook = -1;
            lastStep = now;
            grabbed = false;
            wasPinching = pinching;
            return alpha = 1;
        }
        // A pinch already held elsewhere must not claim this panel's focus.
        if (!pinching) grabbed = false;
        else if (!wasPinching && looking) grabbed = true;
        wasPinching = pinching;
        if (grabbed) looking = true;
        if (looking || lastLook < 0) lastLook = now;
        float target = looking || now - lastLook < 600 ? 1 : RESTING_ALPHA;
        long elapsed = lastStep < 0 ? 0 : Math.min(100, now - lastStep);
        float step = elapsed / (target > alpha ? 80f : 240f);
        alpha = target > alpha ? Math.min(target, alpha + step) : Math.max(target, alpha - step);
        lastStep = now;
        return alpha;
    }

    public boolean wantsInput() { return alpha > RESTING_ALPHA; }
}
