package local.gxr.rotation;

public final class RotationMathTest {
    private static void near(float actual, float expected) {
        if (Math.abs(actual - expected) > 0.00001f) throw new AssertionError(actual + " != " + expected);
    }

    private static void maps(float[] q, float[] input, float[] expected) {
        float tx = 2 * (q[2] * input[2] - q[3] * input[1]);
        float ty = 2 * (q[3] * input[0] - q[1] * input[2]);
        float tz = 2 * (q[1] * input[1] - q[2] * input[0]);
        near(input[0] + q[0] * tx + q[2] * tz - q[3] * ty, expected[0]);
        near(input[1] + q[0] * ty + q[3] * tx - q[1] * tz, expected[1]);
        near(input[2] + q[0] * tz + q[1] * ty - q[2] * tx, expected[2]);
    }

    private static float[] matrix(float[] q) {
        float w=q[0],x=q[1],y=q[2],z=q[3];
        return new float[]{2*(1-2*(y*y+z*z)),4*(x*y+z*w),4*(x*z-y*w),0,
                6*(x*y-z*w),3*(1-2*(x*x+z*z)),6*(y*z+x*w),0,
                8*(x*z+y*w),8*(y*z-x*w),4*(1-2*(x*x+y*y)),0,4,1,-3,1};
    }

    public static void main(String[] args) {
        float[] identity = RotationMath.orientation(0, 0, 0);
        near(identity[0], 1);
        near(identity[1], 0); near(identity[2], 0); near(identity[3], 0);
        maps(RotationMath.orientation(0, 0, 90), new float[] {1, 0, 0}, new float[] {0, 1, 0});
        maps(RotationMath.orientation(0, 90, 0), new float[] {0, 0, 1}, new float[] {1, 0, 0});
        maps(RotationMath.orientation(90, 0, 0), new float[] {0, 1, 0}, new float[] {0, 0, 1});
        maps(RotationMath.orientation(90, 90, 0), new float[] {0, 1, 0}, new float[] {1, 0, 0});
        maps(RotationMath.orientation(0, 0, -90), new float[] {1, 0, 0}, new float[] {0, -1, 0});
        float[] q = RotationMath.orientation(35, -70, 125);
        for (int pitch=-180;pitch<=180;pitch+=45) for (int yaw=-180;yaw<=180;yaw+=45) for (int roll=-180;roll<=180;roll+=45) {
            float[] expected=RotationMath.orientation(pitch,yaw,roll);
            float[] pose=matrix(expected);
            float[] actual=RotationMath.fromMatrix(pose);
            float dot=0;for(int i=0;i<4;i++)dot+=expected[i]*actual[i];
            near(Math.abs(dot),1);
        }
        for(float[] bad:new float[][] {new float[16],new float[15],null}) {
            try {RotationMath.fromMatrix(bad);throw new AssertionError("Invalid matrix accepted");}
            catch(IllegalArgumentException expected){}
        }
        for(int kind=0;kind<4;kind++) {
            float[] bad={1,0,0,0,0,1,0,0,0,0,1,0,4,1,-3,1};
            if(kind==0)bad[0]=Float.NaN;
            if(kind==1)bad[4]=.5f;
            if(kind==2)bad[0]=-1;
            if(kind==3)bad[3]=1;
            try {RotationMath.fromMatrix(bad);throw new AssertionError("Malformed matrix accepted");}
            catch(IllegalArgumentException expected){}
        }
        near(q[0]*q[0] + q[1]*q[1] + q[2]*q[2] + q[3]*q[3], 1);
        float[] handStart = RotationMath.orientation(10, 25, -5);
        float[] parentStart = RotationMath.orientation(0, 40, 0);
        float[] localStart = RotationMath.orientation(15, -10, 30);
        float[] same = RotationMath.grabbed(handStart, handStart, parentStart, parentStart, localStart);
        for (int i = 0; i < 4; i++) near(same[i], localStart[i]);
        float[] wrist = RotationMath.orientation(0, 0, 90);
        float[] parentNow = RotationMath.orientation(0, -25, 0);
        float[] grabbed = RotationMath.grabbed(identity, wrist, identity, parentNow, identity);
        float[] world = RotationMath.multiply(parentNow, grabbed);
        maps(world, new float[] {1, 0, 0}, new float[] {0, 1, 0});
        int[] degrees = RotationMath.degrees(q);
        float[] recovered = RotationMath.orientation(degrees[0], degrees[1], degrees[2]);
        for (int i = 0; i < 4; i++) near(recovered[i], q[i]);
        try { RotationMath.normalize(new float[] {0, 0, 0, 0}); throw new AssertionError(); }
        catch (IllegalArgumentException expected) { }
        for (float invalid : new float[] {Float.NaN, Float.POSITIVE_INFINITY, -181, 181}) {
            try {
                RotationMath.orientation(invalid, 0, 0);
                throw new AssertionError("Invalid angle accepted");
            } catch (IllegalArgumentException expected) { }
        }
        System.out.println("Rotation math: axes, order, normalization, 729 live-pose conversions, invalid matrices and limits passed");
    }
}
