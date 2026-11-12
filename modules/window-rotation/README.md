# Window rotation

The rotation helper supplies Pitch, Yaw, Roll and Reset rotation controls in
the [combined Window Controls module](../../docs/CURVATURE.md). Stock hand
dragging positions the window. Opt-in hand positional rotation follows the
grabbing hand in pitch, yaw and roll. Action opens settings where grab rotation
can be turned off while retaining the sliders. The user verified all three
axes, release and aligned app input on 0.1.18. The 0.1.19 development build
adds menu binding for existing windows and diagnostics; it has not been tested
on the headset. Samsung's grab outline still uses its stock orientation.

The Java source is in `android/local/gxr/rotation/`. It owns a separate
reference to the same CPM scene node, identifies it through `Node.equals()`,
and restores local orientation before releasing that reference. It receives
Home Space eligibility from the shared supervisor. Curvature owns the common
menu height, crop and dismissal.

Use the combined package for curvature, borderless and rotation together.
Keep standalone Rotation off beside the combined runtime. Installation,
recovery, limitations and full build steps are in the
[window guide](../../docs/CURVATURE.md). See [credits](THIRD_PARTY.md).
