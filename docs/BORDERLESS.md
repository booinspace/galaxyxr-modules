# Borderless Home Space windows

Borderless behavior is part of the combined
[Window Controls module](CURVATURE.md). It hides the main app window's white
rim and the resting caption pill. Pointing at the top caption reveals the
pill; leaving it hides the pill after half a second. The caption parent and
stock drag handler remain in place.

The shared agent is [curvature-borderless-agent.mjs](../scripts/curvature-borderless-agent.mjs).
It targets task subgraphs and their caption background through the verified
AZJ2 SystemUI API. It does not remove the view that receives dragging or
change the app's input surface.

Borderless attaches 45 seconds after the shared runtime starts. Fully close
and reopen an app window after that delay. A window restored before the
hooks attach retains its existing decoration.

Use the [combined install, build and recovery guide](CURVATURE.md). Keep a
separate Borderless module off while the combined window runtime is enabled.
