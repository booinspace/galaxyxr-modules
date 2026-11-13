package local.gxr.pins;

public final class FadePolicyTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] ignored) {
        // A ray can intersect the window plane at positive distance while missing the visible app.
        boolean onPanel = PanelRay.hitsPanel(new float[] {0, 0, 2, 0, 0, -1}, 1, 1);
        boolean offPanel = PanelRay.hitsPanel(new float[] {2, 0, 2, 0, 0, -1}, 1, 1);
        check(onPanel && !offPanel);
        FadePolicy nativeHit = new FadePolicy();
        nativeHit.update(0, true, onPanel, true, false);
        float away = 1;
        for (int time = 33; time <= 8000; time += 33) {
            away = nativeHit.update(time, true, offPanel, true, false);
        }
        check(away == FadePolicy.RESTING_ALPHA);
        check(!nativeHit.wantsInput());
        for (int time = 8000; time < 8200; time += 33) {
            away = nativeHit.update(time, true, onPanel, true, false);
        }
        check(away == 1);
        check(nativeHit.wantsInput());

        FadePolicy policy = new FadePolicy();
        check(policy.update(0, true, true, true, false) == 1);
        for (int time = 33; time < 600; time += 33) check(policy.update(time, true, false, true, false) == 1);
        float dimmed = 1;
        for (int time = 600; time < 1100; time += 33) dimmed = policy.update(time, true, false, true, false);
        check(Math.abs(dimmed - FadePolicy.RESTING_ALPHA) < .001f);
        check(!policy.wantsInput());
        for (int time = 1100; time <= 1199; time += 33) dimmed = policy.update(time, true, true, true, false);
        check(dimmed == 1);
        check(policy.wantsInput());
        for (int time = 1200; time < 2300; time += 33) dimmed = policy.update(time, true, false, true, false);
        check(dimmed < .2f);
        check(policy.update(2400, false, false, true, false) == 1);
        check(policy.wantsInput());
        check(policy.update(2500, true, false, false, false) == 1);
        check(policy.update(1, true, false, true, false) == 1);

        FadePolicy grab = new FadePolicy();
        check(grab.update(0, true, true, true, true) == 1);
        for (int time = 33; time < 2000; time += 33) check(grab.update(time, true, false, true, true) == 1);
        for (int time = 2000; time < 3000; time += 33) grab.update(time, true, false, true, false);
        check(!grab.wantsInput());
        for (int time = 3000; time < 3300; time += 33) grab.update(time, true, false, true, true);
        check(!grab.wantsInput());
        FadePolicy elsewhere = new FadePolicy();
        elsewhere.update(0, true, false, true, true);
        for (int time = 33; time < 1500; time += 33) elsewhere.update(time, true, false, true, true);
        check(!elsewhere.wantsInput());
        // Looking at a panel with a pinch already held must not start a grab.
        elsewhere.update(1500, true, true, true, true);
        for (int time = 1533; time < 3000; time += 33) elsewhere.update(time, true, false, true, true);
        check(!elsewhere.wantsInput());
        System.out.println("Fade policy: visible bounds, focus handoff, held grab, stale tracking and restoration passed");
    }
}
