package com.gxr.pt;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The stock AZJ2 log contract used by the upstream passthrough daemon. */
public final class PassthroughPolicy {
    private static final Pattern PUSH = Pattern.compile("alpha=([-+0-9.eE]+), z=(-?\\d+)");
    private static final Pattern TIME = Pattern.compile("^\\s*(\\d+\\.\\d+)\\s");
    public static final String SYS_PUSH = "Setting XR Runtime Server PT layer to";
    public static final String REJECT = "On-device touchpad double tap request rejected in full space mode.";

    public static final class Push {
        public final float alpha;
        public final int z;
        Push(float alpha, int z) { this.alpha = alpha; this.z = z; }
    }

    public static Push push(String line) {
        if (!line.contains(SYS_PUSH)) return null;
        Matcher match = PUSH.matcher(line);
        if (!match.find()) throw new IllegalArgumentException("Unrecognized SystemUI passthrough log");
        float alpha = Float.parseFloat(match.group(1));
        if (Float.isNaN(alpha) || Float.isInfinite(alpha) || alpha < 0 || alpha > 1) {
            throw new IllegalArgumentException("Invalid SystemUI passthrough alpha");
        }
        return new Push(alpha, Integer.parseInt(match.group(2)));
    }

    public static long timestamp(String line) {
        Matcher match = TIME.matcher(line);
        return match.find() ? (long) (Double.parseDouble(match.group(1)) * 1000) : -1;
    }
}
