# Experimental grab-boundary alignment

**0.1.20 is a separate, unvalidated test build. Keep the working 0.1.18 ZIP.**
The working hand-grab implementation and its tested package are preserved in
[commit 3a27dd3](https://github.com/booinspace/galaxyxr-modules/commit/3a27dd376bc16688179617129f7f956b35d6eb35).
This experiment has not been installed or tested on the headset.

## What changes

The rotation helper turns the app's CPM window node. Samsung's movement
outline and highlight belong to its parent, `space-transform-task-N`, so they
can remain upright while the contents tilt. The experiment composes the
window's local transform into those two visual nodes. It includes any
intermediate window leash, scale and position, rather than applying a second
hand estimate. It changes neither the app node nor stock move events,
hit-testing or drag calculations. A curved window still has a rectangular
outline; this experiment addresses orientation, not curved outline geometry.

The implementation observes `HighlightVisual` and `ResizePlaceholderVisual`
on their native update thread. It restores their saved stock transform before
each update or resize, then composes the current content transform afterward.
Nested resize callbacks apply it only once. Window teardown and deactivation
restore the saved transforms before stock cleanup. Runtime shutdown waits for
that restoration before detaching. It never acknowledges cleanup while an
owned visual still needs restoration.

The existing five firmware hashes remain mandatory. The boundary code also
checks 15 exported symbol offsets against the inspected AZJ2 libraries, bounds
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
`gxr-window-curvature-0.1.20-azj2-experimental-disabled.zip` and installs disabled
under the same module ID as Window Controls. It is an update, not a second
module to enable alongside it.

Checks include transform composition for pitch/yaw/roll, nested updates,
stock resize changes, stale handles, changed hierarchies, eligibility loss,
shutdown acknowledgement, vector cleanup and mismatched symbols. A disposable
native C++ process tests real Frida struct returns and allocation cleanup;
that check passed on the ARM64 Mac host. The full build also runs the existing
window runtime, restart and rollback checks. These checks do not establish
visual alignment or performance on the headset.

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
2. Install 0.1.20 as an update, enable it and tap Action. Allow the existing
   startup delays, then open a fresh ordinary app window.
3. Start with a small slider rotation. Grab and move the window; compare its
   outline with the visible content in pitch, yaw and roll. Then enable hand
   rotation and repeat. Check release, app input and resizing.
4. Export logs. `GXR_BOUNDARY_ALIGNED` means the hook applied a transform; it
   does not prove that the visible outline matches. Turn rotation off and
   confirm both the contents and outline return to stock orientation.

If SystemUI crashes, leave the module off and fully reboot. Regain temporary
root and use the existing built-in recovery checks before reinstalling the
saved 0.1.18 ZIP. Do not repeat Soft restarts against a quarantined session.
