package local.gxr.controls;

/** Limits the blend to ordinary Home Space; system and app passthrough keep their own policy. */
public final class PassthroughBlendPolicy {
    private PassthroughBlendPolicy() {}
    public static boolean adjustable(String passthrough,String requestedVr) {
        return requestedVr.equals("HomeSpaceFlinger")
                && (passthrough.equals("Home") || passthrough.equals("Disabled"));
    }
    public static boolean blend(String passthrough,String requestedVr,float alpha) {
        return passthrough.equals("Home") && requestedVr.equals("HomeSpaceFlinger")
                && Float.isFinite(alpha) && alpha>0 && alpha<1;
    }
    public static float alpha(int progress,int minimum,int maximum) {
        if(maximum<=minimum || progress<minimum || progress>maximum)throw new IllegalArgumentException("Invalid passthrough slider range");
        return (float)(progress-minimum)/(maximum-minimum);
    }
}
