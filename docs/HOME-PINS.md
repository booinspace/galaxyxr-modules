# More pinned apps on Home

Window Controls 0.1.30 adds a **50-app Home pin limit** on Galaxy XR AZJ2.
Home keeps its panel size, tile dimensions and five columns. With more than
10 pins, scroll vertically to reach the extra rows. With 10 or fewer, Samsung's
existing centered layout stays in use. Pin, launch, reorder and unpin through
the existing launcher controls.

Candidate 0.1.63 fixes scrolling rows drawing over the system toolbar. The
icons keep their normal size and the grid keeps its existing position and
height; offscreen rows are clipped inside the app area. This layout change
has host checks but still needs a headset test.

This feature is included in the combined Window Controls ZIP and uses its
existing SystemUI runtime. Temporary root and the enabled, running module are
required. On 12 November 2026, the user confirmed that 0.1.30 installed and
started automatically after a GXR Soft restart, with Home and window features
working before opening Action. ADB confirmed the automatic-start version and
live process identity. Extended idle/wake behavior remains unverified.

## Install and test

1. Follow the [combined module update guide](CURVATURE.md#updating-without-a-full-reboot)
   with `gxr-window-curvature-0.1.63-azj2-no-age-test-disabled.zip`.
2. Enable Window Controls and use one KernelSU GXR Soft restart. Keep Home
   awake until the window controls return. This build has no fixed startup-age
   or Borderless delay. Check Home before
   opening Action so manual activation cannot mask a failed automatic start.
3. Open Home and pin an eleventh app using the usual app menu. Scroll within
   the pinned-app area to reach the third row and launch that app. Scroll both
   ways and confirm the clock and system buttons stay unobstructed.
4. Check reordering, unpinning and returning to 10 pins. Also check curvature,
   hand rotation, borders and normal app input, then use Action → Export logs.

After a full power-off, regain temporary root first. This late-loaded root
setup dispatches module services through a GXR Soft restart. Action remains
available for settings, logs and manual recovery.

The module changes no saved pin list. Stopping it restores the stock 10-app
limit and layout. Extra saved pins can be hidden while the module is stopped;
they become accessible again when its Home hooks resume. Unpin the extra apps
before removing the module if you want to return to a list of at most 10.

## How it works

AZJ2's `PinningAppsRepositoryImpl.getLimit()` reads
`config_taskhomePinnedAppsLimit`, whose stock value is 10.
`PinningAppsImpl.getPinnedAppsLimit()` also exposes a cached limit for the UI.
The module raises both Home getters to 50 while its supervisor is alive.
The taskbar branch keeps its original limit.

The Home list uses `FirstPageGridLayoutManager`. Its custom layout draws at
most two rows of five and disables vertical scrolling. Above 10 items, the
module calls that manager's existing `GridLayoutManager` superclass for
layout and scrolling, and lets RecyclerView perform normal focus navigation.
It keeps the same manager instance, span count, panel resources and adapter.
Superclass calls use Frida's direct wrapper to avoid virtual recursion.

Samsung's active AZJ2 overlay sets `clipChildren` and `clipToPadding` to false
on the pinned-app RecyclerView. With scrolling enabled, that allows offscreen
icons to draw above its bounds and over the toolbar. Candidate 0.1.63 enables
both clipping flags only for the expanded grid, retaining each original flag
for restoration when the count returns to 10, the lease expires or the module
stops. The parent layout, icon scale and click targets stay unchanged.

Existing Home views are reflowed on the UI thread. On stop, the hooks are
removed and tracked managers return to the first row before cleanup is
acknowledged. An unavailable Home API leaves the other window features active.
Periodic runtime diagnostics contain `homePins.enabled`, `overflowLayouts`,
`scrollQueries` and any component error.

Source: [Home pin hooks](../scripts/curvature-home-pins-agent.mjs).
The [combined builder](../scripts/build-window-curvature-azj2.py) runs their
tests and the shared restart/restoration checks. Samsung/Google launcher code
was inspected from the user's AZJ2 firmware and is not included in the module.
Curvature is by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules);
the Home integration is by [booinspace](https://github.com/booinspace), using
[Frida](https://frida.re/docs/javascript-api/). See [sources and credits](SOURCES.md).
