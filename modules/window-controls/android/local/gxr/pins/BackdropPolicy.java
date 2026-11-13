package local.gxr.pins;

/** Permits an input/scrim exception only for owned pins above an immersive app. */
public final class BackdropPolicy {
    public static boolean allows(boolean known, boolean sysui, boolean overlay, boolean immersive,
            boolean keyguard, boolean ownedVisible, boolean foreignOverlay) {
        return known && !sysui && overlay && immersive && !keyguard && ownedVisible && !foreignOverlay;
    }
}
