/* Offline unit test for the sender paths that need no root and no tracefs.
 *
 * The relay's real start path needs root, tracefs and the vendor libraries, so
 * this harness includes the sender source (renaming its main) and calls only:
 *   - log_process_context(): the startup diagnostic (one bounded line, stderr);
 *   - on_alarm(): the watchdog's no-op, long-gap-resume, maintenance and
 *     maintenance-overrun cases, including the deferred log-marker reset;
 *   - probe_snapshot()/tracing_enabled() on a host with no tracefs: both must
 *     report "unknown" (-1), never "nothing there" (0), and an unknown read must
 *     leave no probe bits set;
 *   - probe bit helpers, probe_mask_from_arms() and rearm_allowed(): the
 *     startup baseline comes from arm results (not the event-list snapshot) and
 *     the first re-arm obeys the 30 s floor;
 *   - hc_verdict(): the quiet-episode wording must not claim more than the
 *     health check established (in particular it must never say probes are
 *     present when their state is suspect or unknown).
 * The ordinary-stall branch calls _exit(1) and is therefore not run here; that
 * branch is checked structurally in tools/modtest.sh.
 *
 * The diagnostics added for scheduling/tracefs analysis are also covered offline:
 *   - diag_join_lines(): the bounded cgroup field keeps every membership line,
 *     escapes control bytes, never emits a line break, and always marks a value
 *     that did not fit;
 *   - feed_line() accounting: a parsed pten line counts per probe, a foreign
 *     line is not ours, and a malformed line that names one of our events is
 *     counted as invalid rather than foreign;
 *   - state_write_float() without --state-dir is not timed, maintenance phase
 *     names are stable, and schedstat deltas report -1 instead of a fake zero.
 *
 * Build:  cc -O2 -Wall -Wextra -o relay_selftest tools/relay_selftest.c -lm
 * Run:    ./relay_selftest        (exit 0 = pass; "ok"/"FAIL" lines on stdout)
 */
#define main gxr_alvr_program_main
#include "../headset/gxr_alvr.c"
#undef main

static int check(const char *what, int cond) {
    printf("%s %s\n", cond ? "ok" : "FAIL", what);
    return cond ? 0 : 1;
}

int main(void) {
    int bad = 0;

    /* 1. Startup diagnostic: prints exactly one line to stderr. */
    log_process_context();

    /* 2. A fresh progress marker is not a stall. */
    g_maint = 0;
    g_loopTickMs = now_ms();
    int gaps = (int)g_longGaps;
    on_alarm(0);
    bad += check("watchdog ignores a fresh marker", (int)g_longGaps == gaps);

    /* 3. A long gap resumes instead of exiting and counts the gap. The handler
          only sets a flag for the log-write marker; the main loop owns that
          64-bit value, so the handler must not write it. */
    long long old = now_ms() - (LONG_GAP_MS + 5000);
    g_loopTickMs = old;
    g_printStartMs = old;
    g_printReset = 0;
    on_alarm(0);
    bad += check("watchdog resumes after a long gap", (int)g_longGaps == gaps + 1);
    bad += check("watchdog resets the progress marker", g_loopTickMs > old);
    bad += check("watchdog requests the log-marker reset", g_printReset == 1);
    bad += check("watchdog leaves the 64-bit log marker to the main loop",
                 g_printStartMs == old);
    g_printReset = 0;   /* main-loop equivalent, so later checks start clean */

    /* 4. The maintenance window stays exempt even after a long gap. */
    g_maint = 1;
    g_maintStartMs = now_ms();
    g_maintWarned = 0;
    g_loopTickMs = now_ms() - (LONG_GAP_MS + 5000);
    int gaps2 = (int)g_longGaps;
    on_alarm(0);
    bad += check("watchdog stays quiet during fresh maintenance", (int)g_longGaps == gaps2);
    bad += check("fresh maintenance is not warned about", g_maintWarned == 0);

    /* 5. Maintenance that does not return is reported once, without exiting and
          without touching the progress markers (no false stall diagnosis). */
    g_maintStartMs = now_ms() - (MAINT_WARN_MS + 5000);
    g_maintWarned = 0;
    long long tick = g_loopTickMs;
    on_alarm(0);
    bad += check("overrunning maintenance is reported", g_maintWarned == 1);
    bad += check("overrunning maintenance does not move the progress marker",
                 g_loopTickMs == tick);
    g_maint = 0;

    /* 6. Without tracefs the read is UNKNOWN (-1), not "nothing there" (0), and
          an unknown read must not leave a partial mask behind. */
    unsigned pm = PROBE_ALL;
    bad += check("probe_snapshot reports unknown when tracefs is absent", probe_snapshot(&pm) < 0);
    bad += check("unknown probe read leaves no probe bits set", pm == 0);
    bad += check("tracing_enabled reports unknown when tracefs is absent", tracing_enabled() < 0);

    /* 7. Probe bit helpers: pten is bit 0 and the full mask has five bits. */
    bad += check("pten is the mandatory bit", PROBE_PTEN == 1u);
    bad += check("probe_count counts the full mask", probe_count(PROBE_ALL) == 5);
    bad += check("probe_count ignores spare bits", probe_count(PROBE_ALL | 0x80u) == 5);

    /* 8. The startup baseline is built from arm results, never the snapshot:
          a successfully armed optional probe stays required even if the
          observational read failed. 0 = arm success. */
    bad += check("arm mask: pten only", probe_mask_from_arms(0, -1, -1, -1, -1) == PROBE_PTEN);
    bad += check("arm mask: all probes armed", probe_mask_from_arms(0, 0, 0, 0, 0) == PROBE_ALL);
    bad += check("arm mask tracks individual optional failures",
                 probe_mask_from_arms(0, 0, -1, 0, -1) ==
                 (PROBE_PTEN | PROBE_BIT(1) | PROBE_BIT(3)));
    bad += check("arm mask drops a failed mandatory probe",
                 probe_mask_from_arms(-1, 0, 0, 0, 0) == (PROBE_ALL & ~PROBE_PTEN));

    /* 9. Re-arm floor: the startup cleanup starts the clock, so the first
          destructive re-arm waits REARM_MIN_MS; backoff grows and is capped. */
    long long t0 = 1000;
    bad += check("first re-arm blocked before 30 s", rearm_allowed(t0 + 9000, t0, 0) == 0);
    bad += check("first re-arm blocked at 29.999 s",
                 rearm_allowed(t0 + REARM_MIN_MS - 1, t0, 0) == 0);
    bad += check("first re-arm allowed at 30 s", rearm_allowed(t0 + REARM_MIN_MS, t0, 0) == 1);
    bad += check("one failure doubles the floor",
                 rearm_allowed(t0 + REARM_MIN_MS, t0, 1) == 0);
    bad += check("one failure allowed at 60 s",
                 rearm_allowed(t0 + 2 * REARM_MIN_MS, t0, 1) == 1);
    bad += check("backoff caps at REARM_MAX_MS", rearm_backoff_ms(20) == REARM_MAX_MS);
    bad += check("legacy unset floor still allows", rearm_allowed(5000, 0, 0) == 1);

    /* 10. The quiet-episode verdict must match what was verified. */
    char v[192];
    hc_verdict(HC_PROBES_OK, v, sizeof(v));
    bad += check("healthy verdict says healthy", strstr(v, "healthy") != NULL);
    hc_verdict(HC_PROBES_UNKNOWN, v, sizeof(v));
    bad += check("unknown verdict says it could not verify", strstr(v, "could not be verified") != NULL);
    bad += check("unknown verdict does not say healthy", strstr(v, "healthy") == NULL);
    hc_verdict(HC_PROBES_SUSPECT, v, sizeof(v));
    bad += check("suspect verdict says probes are missing", strstr(v, "missing some of our probes") != NULL);
    bad += check("suspect verdict does not claim a re-arm", strstr(v, "re-armed") == NULL);
    hc_verdict(HC_REARMED | HC_PROBES_OK, v, sizeof(v));
    bad += check("re-armed verdict says re-armed", strstr(v, "re-armed") != NULL);
    hc_verdict(HC_REARMED | HC_PROBES_SUSPECT, v, sizeof(v));
    bad += check("failed re-arm verdict does not claim a restore",
                 strstr(v, "did not restore") != NULL);
    hc_verdict(HC_PROBES_SUSPECT | HC_REARM_GAVEUP, v, sizeof(v));
    bad += check("gave-up verdict says re-arming stopped",
                 strstr(v, "automatic re-arming has stopped") != NULL);
    bad += check("gave-up verdict does not promise another attempt",
                 strstr(v, "needed before re-arming") == NULL);
    hc_verdict(HC_REARMED | HC_PROBES_SUSPECT | HC_REARM_GAVEUP, v, sizeof(v));
    bad += check("final failed re-arm verdict says re-arming stopped",
                 strstr(v, "automatic re-arming has stopped") != NULL);
    hc_verdict(HC_PROBES_OK | HC_TRACING_FAILED, v, sizeof(v));
    bad += check("failed re-enable verdict does not claim success",
                 strstr(v, "could not be re-enabled") != NULL);
    hc_verdict(HC_PROBES_OK | HC_TRACING_UNKNOWN, v, sizeof(v));
    bad += check("unreadable tracing_on verdict does not claim healthy",
                 strstr(v, "healthy") == NULL);

    /* F1 regression: an unknown or suspect probe state must never be reported
       as "probes are present" just because tracing_on is the broken part. */
    hc_verdict(HC_PROBES_UNKNOWN | HC_TRACING_UNKNOWN, v, sizeof(v));
    bad += check("unknown probes + unknown tracing does not claim present",
                 strstr(v, "present") == NULL);
    hc_verdict(HC_PROBES_SUSPECT | HC_TRACING_UNKNOWN, v, sizeof(v));
    bad += check("suspect probes + unknown tracing does not claim present",
                 strstr(v, "present") == NULL);
    hc_verdict(HC_PROBES_UNKNOWN | HC_TRACING_FIXED, v, sizeof(v));
    bad += check("unknown probes + re-enabled tracing does not claim present",
                 strstr(v, "present") == NULL);
    hc_verdict(HC_PROBES_OK | HC_TRACING_FIXED, v, sizeof(v));
    bad += check("verified probes + re-enabled tracing says both",
                 strstr(v, "present") != NULL && strstr(v, "re-enabled") != NULL);

    /* 11. The cgroup diagnostic joins EVERY membership line into one bounded
           field: newlines become ';', control bytes become '?', a value that
           does not fit is marked, and nothing is silently lost to the first
           line (cgroup v1 lists one line per controller). */
    char jb[64];
    const char *cg = "0::/uid_1000/pid_42\n1:memory:/x\r\n\x01z";
    size_t jn = diag_join_lines(cg, strlen(cg), jb, sizeof(jb), 0);
    bad += check("cgroup field keeps every membership line",
                 strcmp(jb, "0::/uid_1000/pid_42;1:memory:/x;?z") == 0);
    bad += check("cgroup field reports the bytes it wrote", jn == strlen(jb));
    bad += check("cgroup field never emits a line break",
                 strchr(jb, '\n') == NULL && strchr(jb, '\r') == NULL);
    diag_join_lines("abcdefghij", 10, jb, 5, 0);
    bad += check("cgroup field respects the field cap and marks the cut",
                 strlen(jb) <= 4 && strchr(jb, '+') != NULL);
    diag_join_lines("abc", 3, jb, sizeof(jb), 1);
    bad += check("cgroup field marks a truncated value", strcmp(jb, "abc+") == 0);
    bad += check("a missing event enable reads unknown, not disabled",
                 probe_enable_value("gxr-selftest-no-such-event") == -1);

    /* 12. Per-probe / per-line accounting separates "quiet", "foreign traffic"
           and "our lines do not parse" without touching any file. */
    long long pten0 = g_evPer[0], ln0 = g_lnTotal, lbad0 = g_lnBad, fgn0 = g_lnForeign;
    int fed = feed_line("          gxr_alvr-1  [000] ....  1.000000: pten: idx=0 "
                        "v0=1065353216 v1=1065353216 v2=1065353216 v3=1065353216 "
                        "v4=1065353216 v5=1065353216");
    bad += check("a parsed pten line counts as our event", fed == 1 && g_evPer[0] == pten0 + 1);
    bad += check("a parsed line counts in the line total", g_lnTotal == ln0 + 1);
    feed_line("          other-1     [000] ....  1.000000: someone_else: x=1");
    bad += check("a foreign line is counted separately", g_lnForeign == fgn0 + 1);
    fed = feed_line("          gxr_alvr-1  [000] ....  1.000000: pten: idx=0");
    bad += check("a malformed line of ours is invalid, not foreign",
                  fed == 0 && g_lnBad == lbad0 + 1 && g_lnForeign == fgn0 + 1);
    long long lost0 = g_lnLost, lostev0 = g_evLost;
    feed_line("CPU:0 [LOST 13 EVENTS]");
    bad += check("trace_pipe lost-event notices count separately",
                 g_lnLost == lost0 + 1 && g_evLost == lostev0 + 13);

    /* 13. Timed state writes only exist when --state-dir is set, and the
           maintenance phase stays a plain name (the watchdog prints it). */
    long long writes0 = g_stateWrites;
    state_write_float("dilmin", 3.0f);   /* g_stateDir is NULL in this harness */
    bad += check("a state write without --state-dir is not counted", g_stateWrites == writes0);
    bad += check("maintenance phase names are stable",
                 strcmp(maint_phase_name(MAINT_NONE), "none") == 0 &&
                 strcmp(maint_phase_name(MAINT_REARM), "rearm") == 0 &&
                 strcmp(maint_phase_name(MAINT_RING), "ring-read") == 0 &&
                 strcmp(maint_phase_name(MAINT_TARGET), "resolve-target") == 0);

    /* 14. schedstat deltas: the first sample has nothing to compare against, and
           an unreadable file is reported as unknown (-1), never as zero. */
    long long c1 = 0, r1 = 0, c2 = 0, r2 = 0;
    int sc0 = sched_sample(&c1, &r1);
    bad += check("schedstat sample is positive or honestly unavailable",
                 sc0 != 0 || (c1 > 0 && r1 >= 0));
    int sc1 = sched_delta_ms(&c1, &r1);
    int sc2 = sched_delta_ms(&c2, &r2);
    bad += check("the first schedstat sample reports no delta", sc1 == -1);
    bad += check("schedstat reports a delta or an honest unknown", sc2 == 0 || sc2 == -1);
    if (sc2 == 0)
        bad += check("schedstat deltas are not negative", c2 >= 0 && r2 >= 0);

    /* 15. Direction parsing feeds the per-eye gaze state only for eyes 0/1 and
           only for finite values. Eye 2 must not be silently applied to the
           right eye (the old feed_line treated every non-zero index as right). */
    {
        int de = -1;
        float dv[3];
        bad += check("parse_dir rejects eye index 2",
                     parse_dir("dir: e=2 x=1065353216 y=0 z=1065353216", &de, dv) == -1);
        bad += check("parse_dir rejects a wrapping eye index",
                     parse_dir("dir: e=100000000 x=1065353216 y=0 z=1065353216", &de, dv) == -1);
        bad += check("parse_dir rejects a non-numeric eye index",
                     parse_dir("dir: e=garbage x=1065353216 y=0 z=1065353216", &de, dv) == -1);
        bad += check("parse_dir rejects a non-finite component",
                     parse_dir("dir: e=0 x=2143289344 y=0 z=1065353216", &de, dv) == -1);
        bad += check("parse_dir accepts eye 1",
                     parse_dir("dir: e=1 x=1065353216 y=0 z=1065353216", &de, dv) == 0 &&
                     de == 1 && dv[0] == 1.0f && dv[2] == 1.0f);

        unsigned lseq = g_eyedirSeq[0], rseq = g_eyedirSeq[1];
        long long lms = g_eyedirMs[0], rms = g_eyedirMs[1];
        long long dbad0 = g_lnBad;
        int fed2 = feed_line("          gxr_alvr-1  [000] ....  1.000000: dir: e=2 "
                             "x=1065353216 y=0 z=1065353216");
        bad += check("feed_line rejects eye 2 without touching either eye",
                     fed2 == 0 && g_lnBad == dbad0 + 1 &&
                     g_eyedirSeq[0] == lseq && g_eyedirSeq[1] == rseq &&
                     g_eyedirMs[0] == lms && g_eyedirMs[1] == rms);
        long long dbad1 = g_lnBad;
        int fedn = feed_line("          gxr_alvr-1  [000] ....  1.000000: dir: e=0 "
                             "x=2143289344 y=0 z=1065353216");
        bad += check("feed_line rejects a non-finite direction",
                     fedn == 0 && g_lnBad == dbad1 + 1 &&
                     g_eyedirSeq[0] == lseq && g_eyedirMs[0] == lms);
        int fedl = feed_line("          gxr_alvr-1  [000] ....  1.000000: dir: e=0 "
                             "x=1065353216 y=0 z=1065353216");
        bad += check("feed_line accepts eye 0 and bumps its own timestamp/sequence",
                     fedl == 1 && g_eyedirSeq[0] == lseq + 1 && g_eyedirMs[0] > 0 &&
                     g_eyedirSeq[1] == rseq && g_eyedirMs[1] == rms);
        int fedr = feed_line("          gxr_alvr-1  [000] ....  1.000000: dir: e=1 "
                             "x=1065353216 y=0 z=1065353216");
        bad += check("feed_line accepts eye 1 without bumping eye 0 again",
                     fedr == 1 && g_eyedirSeq[1] == rseq + 1 &&
                     g_eyedirSeq[0] == lseq + 1);
    }

    printf("selftest_bad=%d\n", bad);
    return bad ? 1 : 0;
}
