package local.gxr.controls;

public final class PassthroughBlendPolicyTest {
    private static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args){
        for(String pt:new String[]{"Home","Disabled","Emergency","Lockscreen","Boundary","BoundarySetup","Window","SpatialApi","NotAvailable"})
            for(String vr:new String[]{"HomeSpaceFlinger","AppSpaceFlinger","AppOpenXr","MissingBoundaryInitialSetup","Disabled"}){
                check(PassthroughBlendPolicy.adjustable(pt,vr)==(vr.equals("HomeSpaceFlinger")&&(pt.equals("Home")||pt.equals("Disabled"))));
                for(float alpha:new float[]{0,.01f,.5f,.99f,1,-1,2,Float.NaN,Float.POSITIVE_INFINITY})
                    check(PassthroughBlendPolicy.blend(pt,vr,alpha)==(pt.equals("Home")&&vr.equals("HomeSpaceFlinger")&&alpha>0&&alpha<1));
            }
        check(PassthroughBlendPolicy.alpha(50,0,100)==.5f);
        check(PassthroughBlendPolicy.alpha(20,20,120)==0);
        check(PassthroughBlendPolicy.alpha(120,20,120)==1);
        for(int[] bad:new int[][]{{0,0,0},{0,10,1},{-1,0,100},{101,0,100}}){
            try{PassthroughBlendPolicy.alpha(bad[0],bad[1],bad[2]);throw new AssertionError();}
            catch(IllegalArgumentException expected){}
        }
        System.out.println("PASS: Home-only passthrough blending, critical/app state isolation, endpoints and slider validation");
    }
}
