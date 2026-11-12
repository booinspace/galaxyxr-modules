/* Portable per-eye gaze conditioning state and maths.
 *
 * This header is deliberately free of Android, tracefs and socket code so the
 * same logic can be compiled by a host C compiler and exercised with a fake
 * clock (tools/gaze_math_selftest.c). gxr_alvr.c includes it for the real
 * filter; the trust decision itself stays in gxr_alvr.c because it uses the
 * device's lid/pupil heuristics.
 *
 * Why the time argument is seconds: a One Euro filter is
 *   alpha = 1 / (1 + (1 / (2*pi*fc)) / dt)
 * and fc is in Hz, so dt must be seconds. The relay used to pass milliseconds,
 * which made alpha ~0.99 at 16 ms instead of ~0.13. That is fixed here.
 *
 * The derivative is the difference between the previous RAW sample and the
 * current RAW sample (what the vendor filter does), not between the filtered
 * output and the current sample. Using the filtered output confuses residual
 * tracking error with actual sample velocity and biases the adaptive cutoff.
 *
 * A sample is only fed in when that eye actually has a new raw direction. The
 * caller compares a per-eye sequence/timestamp; re-running this state machine
 * on an unchanged raw sample (at a different compute tick) is not harmless: it
 * advances the filter toward a value it already equals and pollutes dt.
 */
#ifndef GXR_GAZE_STATE_H
#define GXR_GAZE_STATE_H

#include <math.h>
#include <string.h>

#define GXR_GAZE_AXES 3
#define GXR_GAZE_TAU 6.283185307179586476925286766559

/* A dropout longer than GXR_GAZE_GAP_STEPS nominal update periods is
 * represented by at most GXR_GAZE_REACQ_STEPS periods in one filter step. The
 * derivative is reset on that step, so a multi-second hole cannot move the
 * emitted direction in one jump and then have beta amplify it. These are
 * reacquire bounds, not cutoff tunes: normal direction samples (up to ~4x the
 * compute period) still use their real dt. */
#define GXR_GAZE_GAP_STEPS 4.0
#define GXR_GAZE_REACQ_STEPS 1.0

typedef struct {
    int have;                       /* a trusted sample seeded the filter */
    int prev_valid;                 /* raw_prev/t are usable */
    int resync;                     /* next step resets the derivative */
    double t;                       /* seconds of the previous raw sample */
    float raw_prev[GXR_GAZE_AXES];  /* previous RAW direction */
    float s[GXR_GAZE_AXES];         /* filtered direction */
    float dx[GXR_GAZE_AXES];        /* filtered derivative, units/second */
} gxr_gaze_euro;

typedef struct {
    gxr_gaze_euro f;
    float out[GXR_GAZE_AXES];       /* emitted direction (held while untrusted) */
    int have_out;
    int held;
} gxr_gaze_eye;

typedef struct {
    int active;
} gxr_gaze_wink_gate;

static inline int gxr_gaze_finite3(const float v[GXR_GAZE_AXES]) {
    return isfinite(v[0]) && isfinite(v[1]) && isfinite(v[2]);
}

/* One Euro alpha. cutoff_hz <= 0, non-finite values and dt <= 0 return 0
 * rather than a NaN or a divide-by-zero. */
static inline double gxr_gaze_alpha(double cutoff_hz, double dt_s) {
    if (!isfinite(cutoff_hz) || !isfinite(dt_s) || cutoff_hz <= 0.0 || dt_s <= 0.0)
        return 0.0;
    double x = GXR_GAZE_TAU * cutoff_hz * dt_s;
    return x / (1.0 + x);
}

/* A per-eye input timestamp is fresh only inside a non-negative age window. A
 * zero timestamp means "never seen" (the relay's monotonic clock is never 0
 * this late in boot), and a backwards clock step is not freshness. */
static inline int gxr_gaze_fresh(long long now_ms, long long seen_ms,
                                 long long max_age_ms) {
    if (seen_ms <= 0 || max_age_ms < 0) return 0;
    long long age = now_ms - seen_ms;
    return age >= 0 && age <= max_age_ms;
}

static inline void gxr_gaze_eye_init(gxr_gaze_eye *eye) {
    memset(eye, 0, sizeof(*eye));
}

/* No raw sample for this eye: keep the last good emitted direction and make the
 * next real sample reacquire with a reset derivative. A caller that has no
 * have_out yet must emit neutral rather than inventing a centre value here. */
static inline void gxr_gaze_eye_stale(gxr_gaze_eye *eye) {
    eye->held = 1;
    for (int a = 0; a < GXR_GAZE_AXES; a++) eye->f.dx[a] = 0.0f;
    if (eye->f.have) eye->f.resync = 1;
}

/* Feed one raw direction sample.
 *
 * Return:
 *   1  seeded or filtered
 *   0  untrusted: state kept, no seed, no emitted change
 *   2  duplicate/coalesced sample (dt <= 0): no filter step
 *  -1  non-finite input or invalid timestamp
 *
 * nominal_dt_s is the expected update interval (the relay's compute period,
 * floored at its 16 ms design cadence). It only bounds a dropout/reacquire
 * step; it is not a filter coefficient.
 */
static inline int gxr_gaze_eye_sample(gxr_gaze_eye *eye,
                                      const float raw[GXR_GAZE_AXES],
                                      double t_s, int trusted,
                                      double nominal_dt_s,
                                      double fmin_hz, double dcut_hz,
                                      double beta) {
    if (!gxr_gaze_finite3(raw) || !isfinite(t_s) ||
        !isfinite(nominal_dt_s) || !isfinite(fmin_hz) ||
        !isfinite(dcut_hz) || !isfinite(beta))
        return -1;
    /* Match the old fmax(..., 0.01f) floors: a zero/negative --gaze-* cutoff is
     * a silly setting, not a request to freeze the gaze. */
    if (!(fmin_hz > 0.0)) fmin_hz = 0.01;
    if (!(dcut_hz > 0.0)) dcut_hz = 0.01;

    if (!trusted) {
        /* Never seed the filter from an input the trust gate rejected. If it
         * already holds a good output, keep that output and keep the sample
         * clock moving so release uses an ordinary dt, not the hold length. */
        eye->held = 1;
        if (eye->f.have) {
            eye->f.t = t_s;
            memcpy(eye->f.raw_prev, raw, sizeof(eye->f.raw_prev));
            eye->f.prev_valid = 1;
            eye->f.resync = 1;
            for (int a = 0; a < GXR_GAZE_AXES; a++) eye->f.dx[a] = 0.0f;
        }
        return 0;
    }

    if (!eye->f.have) {
        memcpy(eye->f.s, raw, sizeof(eye->f.s));
        memcpy(eye->f.raw_prev, raw, sizeof(eye->f.raw_prev));
        memcpy(eye->out, raw, sizeof(eye->out));
        for (int a = 0; a < GXR_GAZE_AXES; a++) eye->f.dx[a] = 0.0f;
        eye->f.t = t_s;
        eye->f.have = 1;
        eye->f.prev_valid = 1;
        eye->f.resync = 0;
        eye->have_out = 1;
        eye->held = 0;
        return 1;
    }

    double dt = t_s - eye->f.t;
    if (!(dt > 0.0)) {
        /* Same-millisecond event or a backwards clock. Coalesce the latest raw
         * sample so the next derivative uses it, but never divide by zero. */
        memcpy(eye->f.raw_prev, raw, sizeof(eye->f.raw_prev));
        eye->f.prev_valid = 1;
        return 2;
    }

    int gap = 0;
    if (nominal_dt_s > 0.0 && dt > GXR_GAZE_GAP_STEPS * nominal_dt_s) {
        dt = GXR_GAZE_REACQ_STEPS * nominal_dt_s;
        gap = 1;
    }
    if (eye->held || gap) eye->f.resync = 1;

    for (int a = 0; a < GXR_GAZE_AXES; a++) {
        if (eye->f.resync || !eye->f.prev_valid) {
            eye->f.dx[a] = 0.0f;
        } else {
            float raw_dx = (float)((double)(raw[a] - eye->f.raw_prev[a]) / dt);
            double ad = gxr_gaze_alpha(dcut_hz, dt);
            eye->f.dx[a] = (float)(ad * (double)raw_dx +
                                   (1.0 - ad) * (double)eye->f.dx[a]);
        }
        double fc = fmin_hz + beta * fabs((double)eye->f.dx[a]);
        if (!(fc > 0.01)) fc = 0.01;    /* old fmax(..., 0.01f) floor */
        double fl = gxr_gaze_alpha(fc, dt);
        eye->f.s[a] = (float)(fl * (double)raw[a] +
                              (1.0 - fl) * (double)eye->f.s[a]);
    }
    eye->f.t = t_s;
    eye->f.resync = 0;
    eye->f.prev_valid = 1;
    memcpy(eye->f.raw_prev, raw, sizeof(eye->f.raw_prev));
    memcpy(eye->out, eye->f.s, sizeof(eye->out));
    eye->have_out = 1;
    eye->held = 0;
    return 1;
}

/* Wink-shape gate with modest hysteresis. gap is signed for one eye
 * (closed_this - closed_other); enter_gap <= 0 disables the gate, preserving
 * --wink-gap 0. The exit threshold is normally 20% below the entry threshold.
 * A bilateral blink or symmetric squint has both gaps near zero and never
 * enters. */
static inline int gxr_gaze_wink_update(gxr_gaze_wink_gate *gate, float gap,
                                       float enter_gap, float exit_gap) {
    if (!isfinite(gap) || !isfinite(enter_gap) || !(enter_gap > 0.0f)) {
        gate->active = 0;
        return 0;
    }
    if (!isfinite(exit_gap) || exit_gap <= 0.0f || exit_gap >= enter_gap)
        exit_gap = enter_gap * 0.8f;
    if (!gate->active) {
        if (gap > enter_gap) gate->active = 1;
    } else if (gap < exit_gap) {
        gate->active = 0;
    }
    return gate->active;
}

/* Linear eyelid fold animation, with no invented elapsed time. The caller
 * resets boost on a missing face/long gap; the first step after such a gap is
 * zero rather than the old 100 ms shortcut (half a 200 ms wink). */
static inline float gxr_gaze_wink_boost(float boost, int active,
                                       double dt_ms, double ramp_ms) {
    if (!isfinite(boost) || boost < 0.0f) boost = 0.0f;
    if (boost > 1.0f) boost = 1.0f;
    if (!isfinite(dt_ms) || dt_ms <= 0.0 || dt_ms > 500.0) return boost;
    if (!isfinite(ramp_ms) || ramp_ms < 1.0) ramp_ms = 1.0;
    double step = dt_ms / ramp_ms;
    return active ? (float)fmin((double)boost + step, 1.0)
                  : (float)fmax((double)boost - 2.0 * step, 0.0);
}

/* Gaze distrust from the RAW wink shape, before the 200 ms lid-fold ramp has
 * caught up. Kept inside the same soft-lid/pitch-guard bounds as the existing
 * heuristics so a look-down (where the face model collapses openness) cannot
 * turn a small one-eye difference into a freeze. */
static inline int gxr_gaze_wink_untrust(int wink_active, float open,
                                        float pitch_deg, float soft_open,
                                        float pitch_guard) {
    if (!wink_active) return 0;
    if (!isfinite(open) || !isfinite(pitch_deg) ||
        !isfinite(soft_open) || !isfinite(pitch_guard))
        return 0;
    return open < soft_open && pitch_deg > pitch_guard;
}

#endif /* GXR_GAZE_STATE_H */
