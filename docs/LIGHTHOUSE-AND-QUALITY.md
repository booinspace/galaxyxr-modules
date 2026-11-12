# Lighthouse input and OpenXR QUALITY on AZJ2

These findings come from the pinned upstream sources and read-only inspection
of SM-I610 `I610UES3AZJ2`. They separate the PC alignment bridge from Android
controller input and from the headset's camera-rate policy.

## Lighthouse controllers

[QuestLHSync for Galaxy XR](https://github.com/stearnsbq/questlhsync-galaxy-xr)
captures four outward tracking cameras, constructs calibration from the
headset's factory data and sends observations to the PC. The PC
[QuestLHSync driver](https://github.com/CreoleVR/QuestLHSync) uses these to
align the Lighthouse and headset tracking spaces. USB dongles for Index
controllers, Tundra trackers and Vive Tracker 3.0 stay connected to SteamVR.
See the [AZJ2 package guide](../modules/questlhsync/README.md).

That supports the Virtual Desktop/SteamVR path. It does not import the PC's
controller poses, buttons or haptics into Android XR. The inspected server has
no such receive protocol. The inspected AZJ2 CPM interfaces expose pairing,
status and event consumers, but no verified entry point for registering an
arbitrary external 6DoF controller. An ordinary Android mouse bridge would not
provide that input either.

Native Home Space remains an investigation, with no bridge implemented. A
working bridge would need a PC pose/button sender, a verified runtime device
input path, matching coordinates and timestamps, and a haptic return path.
It would also need headset tracking while Home Space has focus; the existing
Virtual Desktop pose stream cannot simply be assumed to stay active then.
This is not evidence that native support is impossible, but the existing
alignment module alone cannot provide it.

The upstream [short-exposure discussion](https://github.com/stearnsbq/questlhsync-galaxy-xr/issues/2)
also matters for Index users: stock-controller activity can affect the camera
frame pattern. The AZJ2 build retains stearnsbq's published behavior. It does
not incorporate the separate fork's camera setter without review and a live
capture test.

## OpenXR QUALITY

[4uva4ek's OpenXR QUALITY](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/openxr-quality)
holds the vendor **HEAD_TRACKING QUALITY** mode while the headset is awake
and a visible app maps the system OpenXR runtime. It invokes the perception
host's Binder shell command `force-set-mode 1 1`. QUALITY requests camera
minimum/maximum **60/60 FPS**; EFFICIENCY requests **30/60 FPS**. These are
requested camera rates, not measured tracking rates or tracking accuracy.

It releases the override on app exit, minimization or sleep. It also releases
at thermal severity 4 or higher and resumes at 2 or lower. While active it
deliberately overrides the stock efficiency transition at severity 3. CPU
and GPU thermal controls stay active. The controller polls approximately once
per second, so its thermal guard is not instantaneous.

It adds no pose prediction, extrapolation or smoothing. It is not a Lighthouse
driver and does not change the tracking performed by the PC's USB dongles.
Home Space alone does not meet its visible-OpenXR-app condition.

**Possible benefit, not measured:** if AZJ2 reduces the tracking cameras to
30 FPS during a supported OpenXR app, holding the 60 FPS request may preserve
camera observations. If the stock request is already 60/60, that mechanism
offers no additional rate. Power and heat can increase. No subjective or
instrumented tracking improvement has been established on this headset.

### AZJ2 compatibility evidence

The inspected vendor perception host and Android Binder libraries match the
upstream identities. Read-only overlay values also match: efficiency trigger
severity **3**, release **2**, power-saver toggle **true**. However,
`services.jar` differs, so the upstream controller correctly refuses AZJ2:

| File | Upstream-supported hash | AZJ2 result |
| --- | --- | --- |
| perception host | `562d027ff604a428b4004882589910be5a21dc1ee7972556929784abd8f44ac5` | Identical |
| libbinder.so | `1da138baee18d16352938d7d33598ed715be8ba31d2bdea23940537001c9f24c` | Identical |
| libbinder_ndk.so | `43392c7b1e812d52578a8bdffe03a08420c877fde922bdfcfdbe537afde72bf2` | Identical |
| services.jar | `1e6f0e8e85020b0ed25bcb387bf7604c9d38c73519ad85df04e15968290b1018` | `ca2d7cdb6a549b7bdbef2c0ef1cab025b2b058f724fc4710911aedb7b9e71555` |

No QUALITY package was built or activated. Porting it needs review of the
changed policy code and then a controlled acquire/release test, camera-rate
measurement and thermal observation. Replacing the hash alone would not
establish compatibility. This keeps the requested investigation separate from
the three experimental headset builds.
