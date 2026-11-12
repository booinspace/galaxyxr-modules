# Window rotation

The rotation helper supplies Pitch, Yaw, Roll and Reset rotation controls in
the [combined Window Controls module](../../docs/CURVATURE.md). Stock hand
dragging positions the window. Opt-in hand positional rotation follows the
grabbing hand in pitch, yaw and roll. Action opens settings where grab rotation
can be turned off while retaining the sliders. Device checks covered all three
axes, release and aligned app input. The user confirmed matching movement
boundaries and rotated resizing with 0.1.23. The current 0.1.24 package keeps
that runtime and removes test labels from its metadata.

The Java source is in `android/local/gxr/rotation/`. It owns a separate
reference to the same CPM scene node, identifies it through `Node.equals()`,
and restores local orientation before releasing that reference. It receives
Home Space eligibility from the shared supervisor. Curvature owns the common
menu height, crop and dismissal.

Use the combined package for curvature, borderless and rotation together.
Keep standalone Rotation off beside the combined runtime. Installation,
recovery, limitations and full build steps are in the
[window guide](../../docs/CURVATURE.md). See [credits](THIRD_PARTY.md).
