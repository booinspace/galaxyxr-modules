# Window boundary alignment

Window Controls keeps Samsung's movement outline and resize corners aligned
with a window rotated by the sliders or by hand. It is included in the
combined build; there is no separate boundary module to install.

The user confirmed boundary alignment, hand rotation in all three axes,
retained orientation after release, app input, curvature, rim/pill hiding,
dragging and planned Soft restart resume on AZJ2. Version 0.1.25 also passed
the extended-reach and correct tilted-resize-direction checks. Its exported
log records 163 corrected resize frames and a movement maximum of 5 m → 50 m;
the exact physical distance was not measured. Version 0.1.26 retains that
runtime. Its in-place install succeeded without a full reboot; the reload
check is pending.
Extended idle/wake stability and other firmware remain unverified.

## Scene ownership and resizing

The rotation helper turns the app's CPM window node. Samsung's movement
outline and highlight belong to its parent, `space-transform-task-N`.
The boundary agent composes the content node's actual local transform into
those two visuals, including intermediate window leashes, scale and position.
It does not apply another hand estimate or change the app node.

AZJ2's `ReformController::GetCurrentRenderState` converts a hit point into
the parent space, subtracts the highlight's position and tests four
axis-aligned corners. Rotating the visual and its collider alone leaves this
calculation in the old frame. The agent converts the hit point back into the
corner test's expected coordinates and passes an owned copy only to that
classifier. The resize solver also receives an owned copy of its local-from-
scene matrix, composed with the inverse content transform. This projects
both start and current drag rays into the tilted window's frame, so outward
motion grows the window and inward motion shrinks it. The original hit,
pointer rays and stock move/resize events are unchanged.

The implementation observes `HighlightVisual` and `ResizePlaceholderVisual`
in `libsysui_jni_soong_vulkan.so` on their native update thread. It restores
the saved stock transform before each update or resize, then composes the
current content transform afterward. Nested callbacks apply it once.
Deactivation and teardown restore the baseline before stock cleanup. Runtime
shutdown waits for restoration before detaching the hooks.

Eligibility follows attached 2D rotation bindings and a two-second heartbeat
deadline. Opening the Curve menu is not required. Leaving Home Space,
disabling rotation or losing the heartbeat revokes eligibility. There is one
SystemUI injector for curvature, borderless, rotation and boundary alignment.

The movement solver temporarily receives ten times its configured maximum
distance for a bound ordinary 2D window. The maximum is restored before that
native call returns, and overlapping calls share one saved baseline so the
multiplier cannot compound. The near limit is unchanged. The exact
`ReformHandler` call sites and solver exports are pinned; unrelated callers
and unbound/system windows retain stock behavior. Distance extension remains
available with rotation controls switched off.

A curved window still has a rectangular outline. Collapsed or nonuniform
transition scales are skipped because the stock TRS setter cannot represent
arbitrary skew. An unexpected injector exit can leave a visual modified until
its scene is recreated; use the [full reboot recovery procedure](CURVATURE.md#recovery-and-logs)
if cleanup is uncertain.

## Firmware checks and build

Use the [combined build command](CURVATURE.md#build) with
`--integrated-borderless --integrated-rotation`. The output is
`gxr-window-curvature-0.1.30-azj2-disabled.zip` and its `.sha256` sidecar.
The former `--experimental-boundary` option is accepted for older build
commands but is no longer needed.

All six [firmware hashes](CURVATURE.md#compatibility-and-runtime) are mandatory.
The boundary code also checks 21 exported symbol offsets against the inspected
AZJ2 libraries, bounds scene traversal, validates weak node handles and rejects
invalid matrices. Native point conversion uses the three-float return ABI
verified by the disposable native check on the ARM64 Mac host. The check also
verifies the by-value optional-matrix argument and owned-copy lifetime used by
the resize solver.

The build runs transform tests for pitch/yaw/roll, scale and translation;
selection of all four rotated corners; unchanged original hits and body
dragging; nested updates; stock resize changes; stale handles and hierarchies;
eligibility loss; cleanup acknowledgement; vector release; and symbol mismatch
rejection, signed inward/outward resize motion, temporary range restoration
and non-compounding nested calls. It also runs the existing shared runtime, restart and rollback
checks. Host tests do not establish compatibility with another firmware or
long-term headset stability.

## Status and diagnostics

Wait for **App window setup: ready** in Action settings before recreating a
test window. A planned Soft restart waits for a 90-second SystemUI process
age, then attaches caption hooks after another 45 seconds. Opening a window's
top menu can bind it earlier but does not retrofit its rim/pill hooks.

Each periodic `GXR_CURVATURE_STATE` entry includes a `boundary` object with
the renderer name, visual callback counts, resize calls, corrected corner-test
and corner-result counts (`resizeHitTests` and `resizeCornerHits`), solver-frame
corrections (`resizeFrames`), distance-call count and last stock/extended
maximum (`distanceCalls` and `distanceLimit`), skip reasons,
a bounded sample of node names, applied transform count and cached visuals.
It logs no matrices, hand positions or quaternions. Use Action's **Export logs**
and the [ADB collection commands](CURVATURE.md#recovery-and-logs) for diagnostics.

The native calls use the [Frida JavaScript API](https://frida.re/docs/javascript-api/).
Entry points and scene ownership come from the exact AZJ2 firmware; no
proprietary firmware image is included. Curvature is by
[BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules). The AZJ2
integration, hand rotation and boundary alignment are by
[booinspace](https://github.com/booinspace); see [sources and credits](SOURCES.md).
