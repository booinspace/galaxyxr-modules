# Experimental grab-boundary alignment

**0.1.23 is a rotated-resize test build, not yet validated on the headset.
Keep the working 0.1.18 ZIP as a fallback.**
The working hand-grab implementation and its tested package are preserved in
[commit 3a27dd3](https://github.com/booinspace/galaxyxr-modules/commit/3a27dd376bc16688179617129f7f956b35d6eb35).
In the 0.1.20 headset test, hand rotation started working after window binding
became available, but the grab outline remained misaligned. The fresh export
contained no fatal error and no `GXR_BOUNDARY_ALIGNED` event. That does not
identify which callback or guard prevented alignment. The 0.1.21 headset test
showed zero highlight, placeholder and resize callbacks while rotation worked.
The original hooks targeted duplicate visual code in
`libspaceflinger_jni_vulkan.so`. Stock startup code configures the UI scene
with `sysui_jni_soong_vulkan`, and read-only live process maps confirmed that
library is loaded in SystemUI. 0.1.22 targets its matching exports instead.

On 12 November 2026 the user confirmed that the grab boundary now follows the
rotated window. The exported 0.1.22 log recorded the UI renderer, 5,090 applied
alignments, live hand-rotation updates and alignment on a recreated app window.
No fatal error or quarantine marker appeared in that export. The user then
confirmed that the module stayed enabled and all window features returned
after a Soft restart. Resizing failed while tilted and worked again after
Reset rotation. The 0.1.22 ZIP is preserved unchanged; extended idle remains
untested.

AZJ2's `ReformController::GetCurrentRenderState` converts the hit point into
the unrotated parent space, then subtracts the highlight's position and tests
four axis-aligned corners. The rotated highlight has a collider below it,
but this corner calculation does not follow its orientation. 0.1.23 converts
the hit point back into the corner test's expected coordinates. It passes
an owned copy only to this classifier; the original hit, pointer ray and
stock resize events are unchanged. Actual resize motion and anchoring still
need the controlled headset check below.

Boundary eligibility now follows the rotation controller's attached 2D window
bindings, with a two-second heartbeat deadline. Opening the Curve menu is not
required to register a rotated window. Leaving Home Space, disabling rotation
or losing the heartbeat revokes eligibility. There is still one injector in
SystemUI; no injection into another process is added.

## What changes

The rotation helper turns the app's CPM window node. Samsung's movement
outline and highlight belong to its parent, `space-transform-task-N`, so they
can remain upright while the contents tilt. The experiment composes the
window's local transform into those two visual nodes. It includes any
intermediate window leash, scale and position, rather than applying a second
hand estimate. It changes neither the app node nor stock move events or drag
calculations. The corner classifier receives the coordinate correction
described above. A curved window still has a rectangular
outline; this experiment addresses orientation, not curved outline geometry.

The implementation observes `HighlightVisual` and `ResizePlaceholderVisual`
on their native update thread. It restores their saved stock transform before
each update or resize, then composes the current content transform afterward.
Nested resize callbacks apply it only once. Window teardown and deactivation
restore the saved transforms before stock cleanup. Runtime shutdown waits for
that restoration before detaching. It never acknowledges cleanup while an
owned visual still needs restoration.

The existing five firmware hashes remain mandatory. The boundary build adds
`/system_ext/lib64/libsysui_jni_soong_vulkan.so`, SHA-256
`f6e34cf42f704c5d3ced9cca18dd392abf4925cde9e30c3b752a34be4102a809`.
The UI library depends on the already pinned `libImpress-jni-vulkan.so`.
The boundary code also
checks 18 exported symbol offsets against the inspected AZJ2 libraries, bounds
scene traversal, validates weak node handles and rejects invalid matrices.
Collapsed or nonuniform transition scales are skipped because the stock TRS
setter cannot represent arbitrary skew. Native API assumptions still require
a headset test. An unexpected injector exit can leave a visual modified until
its scene is recreated; use a full reboot if cleanup is uncertain.

## Build and checks

Use the [combined build requirements](CURVATURE.md#build) and add
`--experimental-boundary` to the command with both `--integrated-borderless`
and `--integrated-rotation`. Without that flag the builder still produces
0.1.19. The experimental output is
`gxr-window-curvature-0.1.23-azj2-experimental-disabled.zip` and installs disabled
under the same module ID as Window Controls. It is an update, not a second
module to enable alongside it.

Checks include transform composition for pitch/yaw/roll, nested updates,
stock resize changes, corrected selection of all four rotated corners,
unchanged original hits and body dragging, stale handles, changed hierarchies,
eligibility loss, shutdown acknowledgement, vector cleanup and mismatched
symbols. A disposable native C++ process tests real Frida struct returns,
including the three-float point conversion result, and allocation cleanup;
that check passed on the ARM64 Mac host. The full build also runs the existing
window runtime, restart and rollback checks. These checks do not establish
visual alignment or performance on the headset.

The `boundary` object in each periodic `GXR_CURVATURE_STATE` entry records
the renderer name,
highlight/placeholder callback counts, resize calls, corrected corner-test and
corner-result counts (`resizeHitTests` and `resizeCornerHits`), skip reasons, a bounded
sample of scene-node names, successful applications and cached visual count.
It logs no matrices, hand positions or quaternions. Zero callback counts mean
the selected entry points were not observed; a skip reason shows where an
observed callback stopped. A successful application still requires a visual
headset check.

Action settings now distinguishes runtime startup from app-window setup. A
planned Soft restart waits for a 90-second SystemUI process age, then attaches
caption hooks after another 45 seconds. Wait for **App window setup: ready**
before closing and reopening a test app. Opening a window's top menu can bind
it earlier, but does not retrofit its rim/pill hooks.

The native calls use the documented
[Frida JavaScript API](https://frida.re/docs/javascript-api/). Entry points and
scene ownership come from the user's exact AZJ2 firmware. No proprietary
firmware image is included. Curvature remains credited to
[BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules); hand rotation
and this visual alignment experiment are by
[booinspace](https://github.com/booinspace).

## Controlled headset check

1. Keep the 0.1.18 package available. Turn Window Controls off, fully reboot
   and regain temporary root with DirtyFrag Autorun off.
2. Install 0.1.23 as an update, enable it and tap Action. Wait for **App window
   setup: ready**, then open a fresh ordinary app window and its top menu.
3. Start with a small slider rotation. Grab and move the window; compare its
   outline with the visible content in pitch, yaw and roll. Then enable hand
   rotation and repeat. Check release and app input. Resize from each corner
   while rolled, then repeat with modest pitch and yaw. Confirm the selected
   corner, size change and fixed opposite corner behave correctly. Reset
   rotation and check ordinary resizing too.
4. Export logs. `GXR_BOUNDARY_ALIGNED` means the hook applied a transform; it
   does not prove that the visible outline matches. Turn rotation off and
   confirm both the contents and outline return to stock orientation.

If SystemUI crashes, leave the module off and fully reboot. Regain temporary
root and use the existing built-in recovery checks before reinstalling the
saved 0.1.18 ZIP. Do not repeat Soft restarts against a quarantined session.
