/* Portable deterministic tests for headset/gaze_state.h.
 *
 * No Android headers, no tracefs, no sockets, no real clock. This is the test
 * the parent can build with any host C compiler:
 *   cc -O2 -Wall -Wextra -o gaze_math_selftest tools/gaze_math_selftest.c -lm
 *   ./gaze_math_selftest
 *
 * Expected alphas are for the unchanged shipped cutoffs (1.5 Hz normal,
 * 0.35 Hz narrowed lid, 1.0 Hz derivative), evaluated at seconds. The old
 * millisecond call produced ~0.993 normal / ~0.972 narrowed-lid at 16 ms.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../headset/gaze_state.h"

static int failures;

static int check(const char *what, int cond) {
    printf("%s %s\n", cond ? "ok" : "FAIL", what);
    if (!cond) failures++;
    return cond;
}

static int near(double a, double b, double tol) {
    return isfinite(a) && isfinite(b) && fabs(a - b) <= tol;
}

static void zero_dir(float v[3]) {
    v[0] = 0.0f; v[1] = 0.0f; v[2] = 1.0f;
}

static void one_x(float v[3], float x) {
    v[0] = x; v[1] = 0.0f; v[2] = 1.0f;
}

/* Seed at raw 0, then feed raw 1 and compare the emitted x to the One Euro
 * alpha for that exact interval. beta = 0 so the adaptive term cannot hide a
 * unit error. */
static int step_alpha(double dt, double fmin, double expected) {
    gxr_gaze_eye eye;
    gxr_gaze_eye_init(&eye);
    float z[3], o[3];
    zero_dir(z);
    one_x(o, 1.0f);
    if (gxr_gaze_eye_sample(&eye, z, 0.0, 1, dt, fmin, 1.0, 0.0) != 1) return 0;
    if (gxr_gaze_eye_sample(&eye, o, dt, 1, dt, fmin, 1.0, 0.0) != 1) return 0;
    return near((double)eye.out[0], expected, 5e-6) &&
           near((double)eye.out[2], 1.0, 1e-6);
}

int main(void) {
    /* 1. Time-unit correction: Hz cutoff + seconds dt. */
    check("1.5 Hz at 16 ms is 0.131037", near(gxr_gaze_alpha(1.5, 0.016), 0.131036594, 1e-6));
    check("0.35 Hz at 16 ms is 0.033990", near(gxr_gaze_alpha(0.35, 0.016), 0.033989875, 1e-6));
    check("1 Hz derivative at 16 ms is 0.091348", near(gxr_gaze_alpha(1.0, 0.016), 0.091347693, 1e-6));
    check("60 Hz nominal alpha", near(gxr_gaze_alpha(1.5, 1.0 / 60.0), 0.135755248, 1e-6));
    check("72 Hz nominal alpha", near(gxr_gaze_alpha(1.5, 1.0 / 72.0), 0.115748280, 1e-6));
    check("30 Hz nominal alpha", near(gxr_gaze_alpha(1.5, 1.0 / 30.0), 0.239057224, 1e-6));
    check("zero dt has no alpha", gxr_gaze_alpha(1.5, 0.0) == 0.0);
    check("NaN dt has no alpha", gxr_gaze_alpha(1.5, NAN) == 0.0);

    /* 2. The state machine realises those alphas at several rates, normal and
          narrowed-lid cutoffs, with the derivative contribution disabled. */
    check("60 Hz step uses normal alpha",
          step_alpha(1.0 / 60.0, 1.5, 0.135755248));
    check("72 Hz step uses normal alpha",
          step_alpha(1.0 / 72.0, 1.5, 0.115748280));
    check("30 Hz step uses normal alpha",
          step_alpha(1.0 / 30.0, 1.5, 0.239057224));
    check("16 ms step uses narrowed-lid alpha",
          step_alpha(0.016, 0.35, 0.033989875));

    /* 3. Once raw input stops moving, the derivative must decay even though
          the filtered output still has substantial tracking error. A second
          identical raw sample distinguishes raw-history from output-history. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float z[3], p[3];
        zero_dir(z);
        one_x(p, 0.1f);
        (void)gxr_gaze_eye_sample(&eye, z, 0.0, 1, 0.016, 1.5, 1.0, 0.01);
        (void)gxr_gaze_eye_sample(&eye, p, 0.016, 1, 0.016, 1.5, 1.0, 0.01);
        double ad = gxr_gaze_alpha(1.0, 0.016);
        double want_first = ad * ((double)p[0] / 0.016);
        check("derivative uses previous raw sample",
              near((double)eye.f.dx[0], want_first, 2e-4));
        double first_out = eye.out[0];
        (void)gxr_gaze_eye_sample(&eye, p, 0.032, 1, 0.016, 1.5, 1.0, 0.01);
        double want_raw = (1.0 - ad) * want_first;
        double want_filtered = ad * (((double)p[0] - first_out) / 0.016) + want_raw;
        check("derivative is distinguishable from filtered-output form",
              near((double)eye.f.dx[0], want_raw, 2e-4) &&
              fabs((double)eye.f.dx[0] - want_filtered) > 0.1);
    }

    /* 4. Deterministic alternating noise at 60 Hz is suppressed with the
          shipped beta=0.01, and the filter stays finite. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float z[3], v[3];
        zero_dir(z);
        (void)gxr_gaze_eye_sample(&eye, z, 0.0, 1, 1.0 / 60.0, 1.5, 1.0, 0.01);
        float mn = 1e9f, mx = -1e9f;
        int finite = 1;
        for (int n = 1; n <= 400; n++) {
            one_x(v, (n & 1) ? 0.1f : -0.1f);
            (void)gxr_gaze_eye_sample(&eye, v, n / 60.0, 1,
                                      1.0 / 60.0, 1.5, 1.0, 0.01);
            finite = finite && isfinite(eye.out[0]);
            if (n > 200) {
                if (eye.out[0] < mn) mn = eye.out[0];
                if (eye.out[0] > mx) mx = eye.out[0];
            }
        }
        check("alternating +/-0.1 noise is suppressed below 0.05 pp",
              finite && (mx - mn) < 0.05f);
    }

    /* 5. Duplicate samples: same timestamp must not advance the filter or
          divide by zero, even if the raw value changed in the same ms. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float z[3], p[3], q[3];
        zero_dir(z);
        one_x(p, 0.2f);
        one_x(q, 0.4f);
        (void)gxr_gaze_eye_sample(&eye, z, 0.0, 1, 0.016, 1.5, 1.0, 0.01);
        (void)gxr_gaze_eye_sample(&eye, p, 0.016, 1, 0.016, 1.5, 1.0, 0.01);
        float out0 = eye.out[0];
        float dx0 = eye.f.dx[0];
        double t0 = eye.f.t;
        int r1 = gxr_gaze_eye_sample(&eye, p, 0.016, 1, 0.016, 1.5, 1.0, 0.01);
        int r2 = gxr_gaze_eye_sample(&eye, q, 0.016, 1, 0.016, 1.5, 1.0, 0.01);
        check("duplicate sample is coalesced", r1 == 2 && r2 == 2);
        check("duplicate sample leaves the filter output alone",
              eye.out[0] == out0 && eye.f.dx[0] == dx0 && eye.f.t == t0);
        check("duplicate sample stays finite", isfinite(eye.out[0]));
    }

    /* 6. An untrusted first sample must not seed the filter or emit a gaze. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float bad[3] = { 0.7f, 0.2f, 0.68f };
        int rc = gxr_gaze_eye_sample(&eye, bad, 0.0, 0, 0.016, 1.5, 1.0, 0.01);
        check("untrusted startup sample is not accepted", rc == 0);
        check("untrusted startup sample does not seed the filter", eye.f.have == 0);
        check("untrusted startup sample does not emit", eye.have_out == 0);
        check("untrusted startup output is neutral",
              eye.out[0] == 0.0f && eye.out[1] == 0.0f && eye.out[2] == 0.0f);
        float good[3];
        zero_dir(good);
        check("first trusted sample seeds",
              gxr_gaze_eye_sample(&eye, good, 0.016, 1, 0.016, 1.5, 1.0, 0.01) == 1 &&
              eye.have_out && eye.out[0] == 0.0f && eye.out[2] == 1.0f);
    }

    /* 7. Hold then release: no snap, derivative reset, ordinary first step. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float z[3], p[3];
        zero_dir(z);
        one_x(p, 1.0f);
        (void)gxr_gaze_eye_sample(&eye, z, 0.0, 1, 0.016, 1.5, 1.0, 0.01);
        check("hold sample is rejected",
              gxr_gaze_eye_sample(&eye, p, 0.016, 0, 0.016, 1.5, 1.0, 0.01) == 0);
        check("hold keeps the last good output and marks held",
              eye.out[0] == 0.0f && eye.held == 1);
        check("release is accepted",
              gxr_gaze_eye_sample(&eye, p, 0.032, 1, 0.016, 1.5, 1.0, 0.01) == 1);
        check("release does not jump to the new raw value",
              eye.out[0] > 0.10f && eye.out[0] < 0.16f);
        check("release resets the derivative", fabs((double)eye.f.dx[0]) < 1e-6);
    }

    /* 8. Dropout reacquires through at most one nominal period; a 1 s hole
          cannot move the output in one near-1.0 step. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float z[3], p[3];
        zero_dir(z);
        one_x(p, 1.0f);
        (void)gxr_gaze_eye_sample(&eye, z, 0.0, 1, 0.016, 1.5, 1.0, 0.01);
        (void)gxr_gaze_eye_sample(&eye, p, 0.016, 1, 0.016, 1.5, 1.0, 0.01);
        float before = eye.out[0];
        (void)gxr_gaze_eye_sample(&eye, p, 1.016, 1, 0.016, 1.5, 1.0, 0.01);
        double cap = gxr_gaze_alpha(1.5, GXR_GAZE_REACQ_STEPS * 0.016);
        check("dropout step is bounded by the reacquire cap",
              (double)(eye.out[0] - before) <= cap + 1e-6 &&
              (double)(eye.out[0] - before) > 0.0);
        check("dropout resets the derivative", fabs((double)eye.f.dx[0]) < 1e-6);
        check("dropout does not snap to the raw sample", eye.out[0] < 0.40f);
    }

    /* 9. Independent per-eye expiration and held output. */
    {
        long long now = 100000;
        check("fresh eye is fresh", gxr_gaze_fresh(now, now - 200, 500));
        check("older eye expires on its own", !gxr_gaze_fresh(now, now - 600, 500));
        check("never-seen eye is not fresh", !gxr_gaze_fresh(now, 0, 500));
        check("backwards timestamp is not fresh", !gxr_gaze_fresh(now, now + 10, 500));

        gxr_gaze_eye a, b;
        gxr_gaze_eye_init(&a);
        gxr_gaze_eye_init(&b);
        float z[3], p[3];
        zero_dir(z);
        one_x(p, 1.0f);
        (void)gxr_gaze_eye_sample(&a, z, 0.0, 1, 0.016, 1.5, 1.0, 0.0);
        (void)gxr_gaze_eye_sample(&b, z, 0.0, 1, 0.016, 1.5, 1.0, 0.0);
        (void)gxr_gaze_eye_sample(&a, p, 0.016, 1, 0.016, 1.5, 1.0, 0.0);
        (void)gxr_gaze_eye_sample(&b, p, 0.016, 1, 0.016, 1.5, 1.0, 0.0);
        float a_out = a.out[0];
        gxr_gaze_eye_stale(&a);
        (void)gxr_gaze_eye_sample(&b, p, 0.032, 1, 0.016, 1.5, 1.0, 0.0);
        check("stale eye keeps its last good output (no centre snap)",
              a.out[0] == a_out && a.out[0] > 0.0f && a.held == 1);
        check("live eye keeps updating independently",
              b.out[0] != a_out && b.held == 0);
    }

    /* 10. Wink threshold hysteresis, including chatter and disabled mode. */
    {
        gxr_gaze_wink_gate g;
        g.active = 0;
        check("wink gate stays off below entry",
              !gxr_gaze_wink_update(&g, 0.20f, 0.35f, 0.28f));
        check("wink gate enters above entry",
              gxr_gaze_wink_update(&g, 0.36f, 0.35f, 0.28f));
        check("wink gate stays on just below entry",
              gxr_gaze_wink_update(&g, 0.30f, 0.35f, 0.28f));
        check("wink gate stays on above exit",
              gxr_gaze_wink_update(&g, 0.29f, 0.35f, 0.28f));
        check("wink gate exits below exit",
              !gxr_gaze_wink_update(&g, 0.27f, 0.35f, 0.28f));

        int chatter_ok = 1;
        g.active = 0;
        (void)gxr_gaze_wink_update(&g, 0.36f, 0.35f, 0.28f);
        for (int i = 0; i < 50; i++) {
            float gap = (i & 1) ? 0.351f : 0.349f;
            if (!gxr_gaze_wink_update(&g, gap, 0.35f, 0.28f)) chatter_ok = 0;
        }
        check("wink gate does not chatter across the entry threshold", chatter_ok);

        g.active = 0;
        check("--wink-gap 0 disables the gate",
              !gxr_gaze_wink_update(&g, 0.90f, 0.0f, 0.0f));
        g.active = 1;
        check("--wink-gap 0 clears an already-active gate",
              !gxr_gaze_wink_update(&g, 0.90f, 0.0f, 0.0f) && g.active == 0);
        g.active = 0;
        check("bilateral blink/squint (zero gap) never enters",
              !gxr_gaze_wink_update(&g, 0.0f, 0.35f, 0.28f));
    }

    /* 11. Raw wink distrust is limited to the closing eye and the same
           soft-lid/pitch-guard bounds as the existing heuristics. */
    check("raw wink distrusts a closing eye on onset",
          gxr_gaze_wink_untrust(1, 0.65f, 0.0f, 0.75f, -20.0f) == 1);
    check("raw wink does not distrust a fully open eye",
          gxr_gaze_wink_untrust(1, 0.80f, 0.0f, 0.75f, -20.0f) == 0);
    check("look-down pitch guard suppresses raw wink distrust",
          gxr_gaze_wink_untrust(1, 0.65f, -25.0f, 0.75f, -20.0f) == 0);
    check("no raw wink means no wink distrust",
          gxr_gaze_wink_untrust(0, 0.65f, 0.0f, 0.75f, -20.0f) == 0);

    /* 12. Non-finite direction never seeds or advances the filter. */
    {
        gxr_gaze_eye eye;
        gxr_gaze_eye_init(&eye);
        float bad[3] = { NAN, 0.0f, 1.0f };
        check("non-finite sample is rejected",
              gxr_gaze_eye_sample(&eye, bad, 0.0, 1, 0.016, 1.5, 1.0, 0.01) == -1);
        check("non-finite sample does not seed", !eye.f.have && !eye.have_out);
        check("finite helper rejects NaN", !gxr_gaze_finite3(bad));
    }

    /* 13. A ramp uses real elapsed time, not a half-wink first-step shortcut. */
    check("wink ramp does not invent time after a gap",
          gxr_gaze_wink_boost(0.0f, 1, 1000.0, 200.0) == 0.0f);
    check("wink ramp does not invent time at zero delta",
          gxr_gaze_wink_boost(0.0f, 1, 0.0, 200.0) == 0.0f);
    check("wink ramp follows 16 ms elapsed time",
          near(gxr_gaze_wink_boost(0.0f, 1, 16.0, 200.0), 0.08, 1e-6));
    check("wink ramp closes fully after 200 ms",
          gxr_gaze_wink_boost(0.0f, 1, 200.0, 200.0) == 1.0f);
    check("wink ramp release is bounded",
          gxr_gaze_wink_boost(0.08f, 0, 16.0, 200.0) == 0.0f);

    printf("gaze_selftest_bad=%d\n", failures);
    return failures ? 1 : 0;
}
