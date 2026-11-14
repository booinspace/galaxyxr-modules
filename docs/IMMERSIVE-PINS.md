# Immersive app pins for AZJ2

This experimental Window Controls update launches a selected Android app through
AZJ2's native overlay-task path. The aim is to keep Symphonium or another ordinary
app over Steam Link without ending its immersive session. The same window runtime
adds the caption controls and fades the panel using eye tracking.

This is an opt-in feature in the combined KernelSU GXR module, not a separate
injector or a modified Symphonium APK. Existing window features use their normal
startup path. Version 0.1.60 observes runtime visibility at startup so hand
outlines can be hidden before a pin is opened. Eye-input sampling starts only
when a marked pin exists.

**Status:** 0.1.54 is device-confirmed for ordinary wrist rotation without opening
a menu, rapid menu dismissal and a second pin after returning from Steam Link.
Immersive pins support wrist rotation, resizing, gaze fading and VRChat joystick
forwarding. The user confirmed that 0.1.56 removes the remaining immersive-view
dimming while preserving pin fading and VR input. Earlier investigation:
the user confirmed overlay visibility, the top pill and dragging with 0.1.32.
Version 0.1.35 crashed
SystemUI during bridge cleanup. Version 0.1.36 kept SystemUI alive, but the pin
launch failed and the module quarantined itself after supervisor heartbeat
expiry. Version 0.1.37 then hung during startup, before `READY` or a pin request;
Android killed the unresponsive SystemUI and its SpaceFlinger death handler
restarted userspace. Version 0.1.38 started successfully and reopened marked
overlay tasks, but Steam Link lost input and dimmed. A later 3.02-second heartbeat
gap caused a clean guarded shutdown; the SystemUI PID stayed unchanged. Saved
tombstones identify Moonlight and Steam Link crashes during that trial; their
relationship to pinning has not been established.
Version 0.1.39 isolates menu polling from the heartbeat, converts gaze into the
hit-test node's reference frame, scopes held pinches to a grab started over that
panel, and covers the compositor's separate dimming factor. Its brightness hook
passed an isolated ARM64 check on the headset, including expiry and detachment.
This does not establish pin focus, fading, protected-UI behaviour, minimisation or
music/audio-focus compatibility in SystemUI. Those still need device testing.
Keep the confirmed 0.1.30 package available until those checks pass.

The 0.1.40 pin trial crashed SystemUI after its zero-delay Borderless startup had
completed. Its runtime log records an access violation in the brightness helper's
`setAllowed`, then another during restoration. The tombstone shows a renderer
callback jumping into the same unmapped native-code page. The helper returned raw
function pointers without retaining their owning CModule or imported storage.
Versions **0.1.39 and 0.1.40 must stay disabled**.

Corrected 0.1.41 retains both resources through shared-agent teardown. Native
disarming now detaches callbacks in a `finally` block, and a brightness-helper
error does not skip the remaining pin cleanup. The production factory's lifetime
failure was reproduced with forced GC in a disposable process. The fix survived
20 forced-GC cycles with both private setter clones, expiry and detachment; its
code was released only after its controller was dropped. This tests lifetime
management, not complete pin interaction in SystemUI. The earlier native test held
the CModule globally, so it did not exercise this failure. The regression harness
is `tests/pin-scrim-lifetime.frida.js`.

The user confirmed a working pinned window in Home Space with 0.1.42. Its exported
version and boot/PID/process-start identity matched the live SystemUI, its injector
remained active, and the log showed one marked pin, a loaded brightness helper,
valid transform/gaze samples and no reported runtime or cleanup error. The crash
buffer was empty after that full reboot. The later Steam Link trial kept the pin
working, but the user saw reversed dimming. A fresh eight-second look-at/look-away
export showed nearly continuous positive hits and requested panel opacity of 1.0.
It did not demonstrate a correctly fading pin.

The 0.1.44 trial stopped after a supervisor heartbeat gap of 2.813 seconds. The
runtime confirmed flat restoration and detached; SystemUI kept the same PID and
the crash buffer was empty. Its pin remained open after the added caption was
removed. Before shutdown, the collision API returned no positive hits, so the
surface-type filter did not establish correct attention or fading.

Candidate 0.1.45 tests the eye ray against the app's centred rectangle and top
caption area using the window node's full world transform. This follows window
movement, rotation and scale without depending on input colliders or opacity.
The fade/focus test includes eight seconds looking outside the rectangle followed
by a return to the app. Geometry checks cover the pill, misses, behind/parallel
rays, pitch/yaw/roll, scale and invalid bounds. The eye-ray direction was also
checked against the exact AZJ2 native routine for identity, pitch, yaw, roll and a
mixed pose. Pinned curved surfaces are approximated by their window rectangle;
exact curved-surface attention is not implemented.

The supervisor now reads settings in its existing bounded menu worker. Its
startup report runs once, outside the heartbeat loop, and rechecks module/process
ownership before publishing. Process start-time checks use shell builtins rather
than a sed/awk pipeline. The 2.5-second lease, target-identity checks, disable and
quarantine rules are unchanged. Tests stall settings and report generation while
checking pulse gaps, invalid-setting failure, disable and PID-identity changes.
These checks do not reproduce the headset's full Steam Link scheduling load;
device fade, focus handoff, brightness and runtime stability need retesting.
Full WSL checks passed. An isolated unprivileged Android-shell trial also kept
five pulses within 1.12 seconds of each other while settings and report work
paused for over three seconds. It used an inherited pipe, wrote the report once
and revoked its launcher token on cleanup. SystemUI's PID and full-boot identity
were unchanged. This did not attach an injector or test the root FIFO/real pins.

The user confirmed 0.1.46 stays running and fades the pin in the correct direction.
Its export matches the live SystemUI identity and shows attention-driven opacity
between 0.18 and 1.0, without a module error or shutdown. It still takes focus from
Steam Link while the pin is attended, dimming the immersive app and interrupting
controller input. A later crash-buffer entry names Steam Link's XRQHandleEvents;
its relationship to pinning has not been established. SystemUI kept the same PID.

Candidate 0.1.47 keeps the real system-overlay focus signal false while only
marked pins are visible above an immersive app. Gaze now changes pin opacity and
local pointer eligibility without handing immersive focus away. A native helper
substitutes an 84-byte per-thread copy of SystemUI's input info, clearing only
its local hasFocusedImmersiveApp byte while the pin needs pointer input. It does
not write the shared input info or change the immersive client's state. The
exact AZJ2 getter and byte layout were checked against the stock image.
The override has a one-second lease and the existing owned-pin/keyguard/SystemUI
scope. At most 32 plain-data copies survive until process exit, so a reference
returned before unhook stays valid. Same-process reinjection remains blocked.
The actual helper passed 20 forced-GC cycles, shared-data isolation, expiry,
unhook and escaping-reference checks in a disposable ARM64 headset process;
SystemUI stayed unchanged.

The user confirmed 0.1.48 keeps Steam Link bright, preserves VRChat joystick input
while looking at the pin, and retains pin interaction and gaze fading. The export
matches versionCode 149 and the live full-boot/PID/process-start identity. Its
immersive samples keep focus=vr with the pin both fully opaque and faded; the
local input-state override counter reached 13,997. No module error or shutdown
was recorded. That build restricted pinned-window rotation to Home Space;
the user confirmed ordinary Home Space rotation works. Extended idle/wake,
minimise/restore and protected-UI interaction remain separate checks.

The separate **0.1.56 startup timing test** is based on 0.1.55 and removes its
extra 45-second Borderless wait. Borderless is queued on the next event-loop turn
after agent initialization; the 90-second SystemUI process-age guard, heartbeat,
firmware checks and quarantine remain. Build it by adding `--no-borderless-delay`
to the combined build command. The default build produces 0.1.55.
Both ZIPs update the same module ID. GXR requires increasing version codes, so
an older ZIP cannot be installed directly over a newer build as a downgrade.

The current candidate supplies only the live, primary-user, explicitly marked
overlay task IDs to the existing rotation controller. Their orientation survives
gaze changes; new immersive grabs additionally require an attended pin and the
same protected-UI/VR-focus scope as pointer input. Ordinary Home Space rotation
keeps its existing path. The existing native boundary and resize-direction fixes
now also receive those pin IDs. Enable **Rotation** and **Rotate while grabbing**
in Window Controls settings, then grab the pinned window's top pill and twist
your wrist in pitch, yaw or roll.

Pinned panels now enable the stock resize handles for resizeable apps and use
AZJ2's app minimum sizes, maximum sizes and corner dimensions. A resize-only
listener commits the new Android task bounds and returns the confirmed size to
the stock compositor callback. It ignores focus-request events, so moving or
resizing the pin does not restore Home Space focus over Steam Link. Requests
time out after five seconds; cleanup restores the original reform flags, nullable
size limits and boundary dimensions, while preserving the app's newly resized
bounds. Diagnostics include the current panel size and outstanding completion
count. Test corner resizing while Steam Link is immersive, then verify app input,
wrist rotation, fading and VR joystick forwarding together.

Host checks exercise the actual Java helpers with Android doubles and the
Kotlin/coroutines JARs already included in Android's command-line tools. They
cover all three rotation axes, task isolation, size-limit restoration, resize
completion, timeout and cancellation. `tests/PinResizeAbi.java` is a read-only
check of the required methods in the stock AZJ2 APK, run in a disposable process.
Neither check proves the visible resize handles or immersive rotation work.

The 0.1.50 Steam Link launch trial stopped on a 2,908.5 ms supervisor heartbeat
gap, exceeding its 2,500 ms cutoff. It restored all owned tasks and quarantined;
the exported and live SystemUI identity remained
`b73d3fc9-b4c8-42b6-bec3-0630ecaf5866:8827:506957`. No new native crash or resize
error was recorded, and no resize completion was pending. Android's logs show
skipped frames during the launch, but do not establish which part delayed the
heartbeat. The earlier native Steam Link crash in the crash buffer predates
this trial.

Candidate 0.1.52 aligns supervisor, pinned-panel, pin-menu, rotation and
supervised-curvature watchdogs at five seconds. The older curvature session's
separate three-second watchdog is updated too; changing only the top-level
cutoff would have left that failure path. The one-second native input/brightness
leases, 150 ms eye freshness and existing hand-sample validation stay unchanged.
Native overrides therefore still fall back promptly on stale data. A genuinely
missing supervisor now has up to five seconds to trigger the complete rollback.
Every transmitted pulse is timestamped in the service log, and the agent reports
its largest received heartbeat gap. The regression checks cover the observed
2.91-second gap, renewed operation, matching curvature-session duration and
expiry at five seconds. Firmware pins, the 90-second startup guard and crash
quarantine remain in force.

The user confirmed that 0.1.52 stayed running in Steam Link with working wrist
rotation and resizing. The matching export records a pin changing from
1536×960 to 2127×1768, 82 rotated-resize solver frames, applied wrist grabs and
VR focus retained while gaze fading continued. The largest received heartbeat
gap was 2349 ms. After returning to Home Space, a later queued menu attachment
reported `Menu closed before attachment`; the supervisor stopped and restored
all owned tasks. Its heartbeat was only 49 ms old, and the native crash buffer
was empty. This was a separate menu-lifecycle failure, not the watchdog limit.

Candidate 0.1.54 marks a ticket closed when its menu disappears before the queued
owner callback runs, or when its curvature session has already ended. It creates
no controls in either case. The supervisor prunes that cancelled ticket while
keeping genuine attachment errors fatal. Regression checks reproduce rapid
menu dismissal, queued cancellation, stale sessions and real constructor errors.

Ordinary Home Space windows do not require pinning for wrist rotation. The user
confirmed that opening a window's menu made rotation work: that path registers
an existing caption, while the old startup hook saw only captions created after
the runtime began. The candidate also enumerates the caption director's existing
decorations on its actual handler at startup. It registers only caption windows;
package, 2D-rendering, Home Space/pin and live-node checks remain. Discovery is
cancelled on shutdown. The real rotation-controller fixture verifies a restored
caption can rotate without opening its menu or pinning the app.

The user confirmed both 0.1.54 fixes and the pin/Steam Link/second-pin sequence.
The export contains no fatal error or shutdown; a 2.91-second supervisor gap was
tolerated. A nonfatal closed-node message from rim cleanup remains in that log.
The live CPM dump shows Steam Link's layers at alpha 1.0, no color-scale override,
and the SystemUI runtime layer's scrim target at zero. These checks do not explain
the remaining small brightness reduction by themselves.

Candidate 0.1.56 additionally suppresses `spaceflinger::Scrim::SetAlpha`, the
renderer mesh separate from CPM's layer metadata. It changes only the incoming
float alpha while the existing one-second lease permits owned pins over an
immersive app, with no genuine SystemUI, foreign overlay or keyguard visible.
Expiry, removal and shutdown restore stock calls; the animated target and panel
gaze fade are not changed. The exact AZJ2 export address and prologue are checked
before attachment. Diagnostics report sampled frames, suppressed positive-alpha
frames and the mean requested alpha, so an ineffective override is distinguishable
from a confirmed brightness fix.

The user confirmed normal immersive brightness, pin fading and joystick input
with 0.1.56. Its export matches the live boot/PID/process-start identity and
records 3,784 suppressed positive-alpha fullscreen-scrim frames, with mean
requested alpha 0.232. The module remained running without a fatal error or
shutdown through the exported test. Extended idle/wake and other immersive
applications have not been retested.

## Android focus and hand outlines

After interacting with a pin in 0.1.57, Steam Link could remain visible while
the pin kept Android task focus. A live capture showed Symphonium focused,
Steam Link visible in full-space mode, and XR focus assigned to SystemUI.
The user could restore controller input by selecting Steam Link in Recents.
This is separate from the module's existing pointer eligibility and scrim
override, which remained active in the export.

Version 0.1.60 checks the caption organizer's current task list on its owner
handler. While only owned pins are visible over immersive content, a focused
owned pin returns Android focus to the unique visible primary-user immersive
task through `IActivityTaskManager.setFocusedTask`. It does not relaunch the app
or change window order. No focused pin, hidden tasks, another user, ambiguous
immersive tasks, foreign overlays, system UI, keyguard or an expired supervisor
lease cause no focus transfer. Successful transfers are limited to one per
second and reported as `androidFocusReturns` and `androidFocusTarget`.

The same version uses AZJ2's `HandRenderer::SetDrawMode` to hide system hand
outlines in immersive view. The stock `Hand::Update` calls this setter each
frame; its verified enum defines `NONE` as zero. A separate one-second lease
covers pure immersive view as well as owned pins over it. Looking at or holding
a pin keeps the stock draw mode, and looking away suppresses the outlines.
System UI, keyguard, foreign overlays, lease expiry and teardown restore stock
calls. The hand pose and gesture streams keep running. This affects SystemUI's
outline renderer, not hands drawn by an immersive app or the separate
passthrough hand-breakthrough setting. Diagnostics include `hiddenHands`.

Host tests cover focus selection/debounce and hand lease expiry, invalid modes,
clock failure, cleanup and native-owner retention. The ARM64 fixture passed
20 forced-GC cycles on the Mac using the real native CModule and private setter
clones, with an adapter for the host's monotonic-clock ID. Read-only checks of
the real AZJ2 interfaces also passed on the headset. The user then confirmed
controller recovery and attention-controlled hand outlines working in 0.1.60.
Extended idle/wake and other immersive apps have not been retested.

## Use

1. Install the experimental combined update through KernelSU GXR as an in-place
   update. It installs disabled. Enable Window Controls and use the existing
   coordinated Soft restart procedure; wait for its normal startup guard.
   If the previous session is quarantined, leave Window Controls off, fully reboot,
   regain temporary root with DirtyFrag Autorun off, then install the update while
   it stays off. Enable it and press Start in settings; no extra Soft restart is
   needed for this cold-boot test.
2. Close Symphonium's existing ordinary windows before pinning from settings.
   Android can otherwise reuse an ordinary task. The launcher now rejects that
   case before changing the overlay allowlist. Alternatively, use the window's
   **Pin app → Reopen and pin** menu action to reopen that specific window.
3. Open **Window Controls → Action → Immersive app pins**. Symphonium's package,
   app.symfonik.music.player, is prefilled. Choose **Pin app**.
4. Open Steam Link and check whether the pinned app remains visible. The overlay
   should retain a caption with its usual minimise action. The Action page also
   has **Minimise pinned app** and **Restore pinned app** controls for the last
   selected package.
5. Look at the panel, then away from it. The candidate holds full opacity for
   600 ms, fades to 18%, and restores full opacity over 80 ms when looked at.
   These are policy timings, not measured end-to-end latency.
   While attended, the pin receives Android pointer input and the immersive app
   retains its focus and controller input. An attended pinch holds the pin's
   pointer eligibility until release. These concurrent-input behaviours are the
   current candidate's intent and still need device confirmation. Tracking loss
   restores full pin opacity so it can be closed.

Pinning additional apps uses their installed package names. Version 0.1.68 also
allows preinstalled apps, including YouTube XR's Home Space panel, through the
same menu and launcher checks as user-installed apps. Apps must have a normal
launcher and pass the existing XR launch-mode checks. Core system UIDs below
10000, SystemUI and KernelSU remain excluded. This does not force immersive XR
activities into overlay mode. YouTube's singleTask launcher still uses **Reopen
and pin** so Android does not reuse its ordinary window; save any work first.
The headset owner confirmed the 0.1.68 preinstalled-app pinning update working
after the on-device YouTube eligibility check passed. Other preinstalled apps
and transitions into their own immersive modes need individual testing.

The runtime limits itself to eight marked panels. Minimise should hide the window without
force-stopping its app. **Close all pinned windows** removes only tasks launched
with this feature's marker. Audio playback and audio-focus behaviour remain the
music app's responsibility and need testing alongside Steam Link.

The window pill's menu also has a **Pin app** row with a pin icon. Save your work,
press it, then confirm **Reopen and pin**. The supervisor checks the selected task
and reopens that window through the same guarded launcher. This can discard
unsaved activity state; it does not force-stop the app or clear its storage.
The menu shows completion or failure without opening KernelSU settings.
The 0.1.38 trial confirmed successful reopening through the pill menu. Its full
completion feedback and interaction alongside Steam Link still need testing.

Opening the Action page may itself leave the immersive app. The intended ongoing
workflow is to pin before entering Steam Link, then use the panel's normal caption.
Restoring a minimised overlay from the ordinary launcher/recents also needs
verification; a permanent in-immersive summon gesture is not implemented.

## How it works and rollback

The launcher temporarily changes the exact component in Android's overlay
allowlist using KernelSU GXR's resetprop -n. It restores the previous values
when the launch returns, including on errors. It does not write persistent
property storage, grant permanent app permissions, change SELinux or install an
OpenXR session. It preserves property changes made by another owner.

The stock window manager creates desktop mode 4, its native overlay mode. Those
tasks remain separate from the immersive app. Stock SystemUI omits their normal
captions, so the shared agent adds captions only to explicitly marked primary-user
overlay tasks. Keyguard and stock overlay visibility remain authoritative.
The marker is an Intent category: AZJ2 filters extras from task reports but keeps
categories, so ordinary intent extras cannot be used to identify these windows.
The candidate enables stock movement on the marked panel's transform, with resize
off, and closes its captions on their own Shell handler. It does not add a second
drag engine or move the ordinary Home Space task into an immersive container.

The gaze reader reads the eye/aim action from AZJ2's input batch before it is
dispatched to individual devices, without altering its input. The helper
subscribes to the window node's world transform through Samsung's existing
listener factory and converts the ray to that window's local coordinates. It
tests the visible app rectangle and a small area above it for the caption pill.
A pinch must start over the panel to hold its drag focus; a pinch already
held elsewhere cannot prevent fading. Coordinates
are transient and are not written to logs or sent over the network. Logs contain
task IDs and counters. Missing, invalid or stale gaze data restores full opacity.
The helper multiplies stock opacity rather than making a minimised window visible.
While an immersive app renders and only this module's pins are visible, the new
candidate requests a transparent scrim on SystemUI's runtime layer and temporarily
keeps the system-overlay focus signal clear for the immersive app. The attended
pin's pointer path uses a local input-state copy instead of changing global focus.
Earlier builds cleared focus only while the panel was faded; that interrupted VR
input and dimmed the immersive app whenever the user looked at the pin.
AZJ2 also applies a separate per-renderer dimming factor. The candidate overrides
that factor only while the same owned-pin scope is valid, leaving the panel's own
opacity fade intact. It verifies both setter symbols, offsets and all three
instructions before hooking. The native override expires after one second without
renewal and is disarmed for system UI, keyguard, overlay changes and shutdown.
It retains no renderer pointers: the stock setters continue running and provide
their normal values when the override is inactive.
It restores stock handling for system UI, keyguard, foreign overlays, unknown
state or supervisor expiry. It retains the runtime layer's stock visibility and
SystemUI role. The 128 scope combinations are covered by a host policy check;
runtime focus, controller forwarding and protected-UI behaviour need device tests.

Before a normal module stop/update, the root controller closes marked overlay
windows; it does not force-stop the music app. The shared cleanup restores opacity
and removes its captions and hooks. A failed cleanup keeps the existing guard in
place. A full reboot discards the in-memory allowlist edits and the temporary root
session. Keep DirtyFrag Autorun off.

If the candidate misbehaves, leave it disabled and export logs through the existing
Window Controls recovery path. Keep the working package until the candidate is
confirmed. Do not bypass an existing crash quarantine to force another attachment.
After a caption-cleanup error, switch Window Controls off and fully reboot before
updating. Regain temporary root with Autorun off, install the update while the
module stays off, then enable it and open Action. A Soft restart cannot clear a
failed cleanup acknowledgement from that same full boot.

## Build and attribution

Use the existing [Window Controls build steps](CURVATURE.md). The candidate
builder produces gxr-window-curvature-0.1.41-azj2-experimental-disabled.zip;
`--no-borderless-delay` produces the 0.1.42 startup-test ZIP.
It pins the SystemUI, framework, ART and renderer hashes plus the exact AZJ2
services.jar. Neither firmware binaries nor decompiled vendor sources are
distributed.

The 0.1.35 tombstone records a jump through bytes matching a partially restored
ART interpreter-bridge entry point after the injector detached. The same invalid
jump was reproduced outside SystemUI. The local bridge patch suspends ART threads
while writing or restoring quick-code entry points and retains retired JNI
callbacks through script teardown for calls still in flight. Suspension alone
still failed the isolated cleanup test; the callback-lifetime guard was also
needed. The minimal combined patch passed all five follow-up trials, and the
subsequent 0.1.36 failure did not crash SystemUI.

The 0.1.36 investigation reproduced a Binder failure with even `cmd activity
help` when output was inherited from a protected root log file. Pipe output
worked. The launcher now uses pipes and drains output while retaining its
10-second timeout and failed-launch cleanup. Android's shell also closes
descriptor 3 when starting another shell unless it is explicitly passed; the
supervisor now passes the menu reply channel explicitly.

Android froze KernelSU after entering Steam Link's immersive activity. Root
shells started by its WebUI remained in the manager's app cgroup; the installed
KernelSU `su` command was verified to move a child to the root cgroup. Manual
startup now uses that command for the supervisor, matching the separation used
by normal module services. The service log records the supervisor's cgroup for
the next device check. This addresses the observed freezer hazard; the full
0.1.38 supervisor ran in the root cgroup, but its synchronous menu polling still
ran in the heartbeat loop. Version 0.1.39 runs at most one poll worker alongside
that loop, revokes its launcher token and reaps the worker on shutdown. A generated
controller test blocks menu polling for four seconds while checking that the
2500 ms heartbeat deadline is still met. The deadline and quarantine are unchanged.

The new dispatch change is based on
[Kolektori's upstream proposal](https://github.com/frida-packages/frida-java-bridge/pull/401),
commit `dde975ddd6cc8ea8e8667d9a6f5629b22ff16a1c`. It removes a mutex from the
method-call path that can interact with Android's thread suspension. Local
corrections publish completed mapping lists atomically, including during removal.
On AZJ2, a four-reader native test observed 1,376 missing lookups with the
upstream deletion code and zero with the corrected code. The corrected bridge
also passed two isolated startup/GC/unhook/detach trials. The old bridge passed
those short trials too: they did not reproduce the SystemUI hang or prove its
cause. The candidate logs each initialization stage for the next controlled test.
Retired mapping snapshots remain allocated until the SystemUI process exits;
they are not freed while another thread may still use them.

The overlay launcher, caption integration and eye-fade code are by
[booinspace](https://github.com/booinspace). The shared curvature/runtime foundation
is by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules);
[sources and component licensing](SOURCES.md) apply to the combined package.
The dispatch adaptation credits Kolektori; atomic publication corrections are
by booinspace. It retains the bridge's existing license and includes the patch.
This extends behaviour beyond Android XR's standard
[single-app Full Space model](https://developer.android.com/design/ui/xr/guides/foundations).
