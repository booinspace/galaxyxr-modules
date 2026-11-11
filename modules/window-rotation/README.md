# Window rotation

The rotation helper supplies Pitch, Yaw, Roll and Reset rotation controls in
the [combined Window Controls module](../../docs/CURVATURE.md). Stock hand
dragging positions the window; rotation uses sliders and applies on release.

The Java source is in `android/local/gxr/rotation/`. It owns a separate
reference to the same CPM scene node, identifies it through `Node.equals()`,
and restores local orientation before releasing that reference. It receives
Home Space eligibility from the shared supervisor. Curvature owns the common
menu height, crop and dismissal.

Use the combined package for curvature, borderless and rotation together.
Keep standalone Rotation off beside the combined runtime. Installation,
recovery, limitations and full build steps are in the
[window guide](../../docs/CURVATURE.md). See [credits](THIRD_PARTY.md).
