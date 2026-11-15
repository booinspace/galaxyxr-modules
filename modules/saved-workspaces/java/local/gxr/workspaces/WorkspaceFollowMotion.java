package local.gxr.workspaces;

/** One smoothed room-relative transform for the whole layout, independent of window content rotation. */
public final class WorkspaceFollowMotion {
    private float[] originHead,originLayout,currentHead,currentLayout;
    private final float[] velocity=new float[4];
    private long lastTime;
    private boolean translating,turning;
    public WorkspaceFollowMotion(float[] facing,float[] layout,long now){rebase(facing,layout,now);}
    private static float yaw(float[] pose){return (float)Math.atan2(pose[8],pose[10]);}
    private static float angle(float value){return (float)Math.atan2(Math.sin(value),Math.cos(value));}
    /** Removes scale and the two-metre forward offset requested from CPM. */
    public static float[] head(float[] facing){
        float[] value=WorkspaceMath.checked(facing),out=WorkspaceMath.identity();
        double length=Math.sqrt(value[8]*value[8]+value[9]*value[9]+value[10]*value[10]);
        float heading=yaw(value),c=(float)Math.cos(heading),s=(float)Math.sin(heading);
        out[0]=c;out[2]=-s;out[8]=s;out[10]=c;
        for(int i=0;i<3;i++)out[12+i]=value[12+i]+(float)(2*value[8+i]/length);
        return WorkspaceMath.checked(out);
    }
    public void rebase(float[] facing,float[] layout,long now){
        originHead=head(facing);currentHead=originHead.clone();originLayout=WorkspaceMath.checked(layout);
        currentLayout=originLayout.clone();pause(now);translating=false;turning=false;
    }
    public void pause(long now){java.util.Arrays.fill(velocity,0);lastTime=now;}
    private float damp(float current,float target,int axis,float rate,float seconds){
        float difference=current-target,step=(velocity[axis]+rate*difference)*seconds;
        float decay=(float)Math.exp(-rate*seconds);
        velocity[axis]=(velocity[axis]-rate*step)*decay;
        return target+(difference+step)*decay;
    }
    public float[] update(float[] facing,long now){
        float[] target=head(facing);
        if(now<lastTime)throw new IllegalArgumentException("Follow clock moved backwards");
        float seconds=Math.min(50,now-lastTime)/1000f;lastTime=now;
        float distance=0,speed=0;
        for(int i=0;i<3;i++){distance+=(target[12+i]-currentHead[12+i])*(target[12+i]-currentHead[12+i]);speed+=velocity[i]*velocity[i];}
        distance=(float)Math.sqrt(distance);
        if(distance>.12f)translating=true;
        else if(distance<.005f&&speed<.0001f){translating=false;for(int i=0;i<3;i++)velocity[i]=0;}
        if(translating)for(int i=0;i<3;i++)currentHead[12+i]=damp(currentHead[12+i],target[12+i],i,12f,seconds);
        float currentYaw=yaw(currentHead),delta=angle(yaw(target)-currentYaw);
        if(Math.abs(delta)>Math.toRadians(40))turning=true;
        else if(Math.abs(delta)<Math.toRadians(1)&&Math.abs(velocity[3])<Math.toRadians(2)){turning=false;velocity[3]=0;}
        if(turning){
            float heading=damp(currentYaw,currentYaw+delta,3,5f,seconds);
            float maximum=(float)Math.toRadians(60)*seconds;
            if(Math.abs(heading-currentYaw)>maximum){heading=currentYaw+Math.copySign(maximum,heading-currentYaw);velocity[3]=Math.copySign((float)Math.toRadians(60),heading-currentYaw);}
            float c=(float)Math.cos(heading),s=(float)Math.sin(heading);
            currentHead[0]=c;currentHead[2]=-s;currentHead[8]=s;currentHead[10]=c;
        }
        currentLayout=WorkspaceMath.multiply(WorkspaceMath.multiply(currentHead,WorkspaceMath.inverse(originHead)),originLayout);
        return currentLayout.clone();
    }
    public float[] placement(){return currentLayout.clone();}
    public static boolean near(float[] a,float[] b){
        for(int i=0;i<16;i++)if(Math.abs(a[i]-b[i])>.001f)return false;return true;
    }
    /** Keep slow movement fluid without tightening the tolerance used to recognize user input. */
    public static boolean placementChanged(float[] a,float[] b){
        for(int i=0;i<16;i++)if(Math.abs(a[i]-b[i])>.0001f)return true;return false;
    }
    /** Retains bounded in-flight placements so a late own callback is not mistaken for a drag. */
    public static final class WindowPose {
        private static final int MAX_PENDING=8;
        private static final class Placement {
            final float[] world;final long stamp,time;
            Placement(float[] world,long stamp,long time){this.world=WorkspaceMath.checked(world);this.stamp=stamp;this.time=time;}
        }
        private float[] relative,observed;
        private final java.util.ArrayDeque<Placement> pending=new java.util.ArrayDeque<>(),recent=new java.util.ArrayDeque<>();
        private Placement acknowledgedPlacement;
        public WindowPose(float[] actual,float[] anchor){external(actual,anchor);}
        private void remember(Placement value){recent.addLast(value);while(recent.size()>MAX_PENDING)recent.removeFirst();}
        private void external(float[] actual,float[] anchor){
            relative=WorkspaceMath.relative(anchor,actual);observed=actual.clone();
            pause();
        }
        public void pause(){while(!pending.isEmpty())remember(pending.removeFirst());acknowledgedPlacement=null;}
        private void healthy(long now){
            if(!pending.isEmpty()&&now-pending.peekFirst().time>500)throw new IllegalStateException("Window placement was not acknowledged; following stopped");
        }
        public boolean observe(float[] actual,long acknowledged,float[] anchor,long now){
            WorkspaceMath.checked(actual);Placement own=null;
            for(Placement value:pending)if(value.stamp==acknowledged){own=value;break;}
            if(own!=null){
                Placement value;do{value=pending.removeFirst();remember(value);}while(value!=own);
                acknowledgedPlacement=own;
            }else for(Placement value:recent)if(value.stamp==acknowledged){own=value;break;}
            if(near(actual,observed)){healthy(now);return false;}
            if(own!=null&&near(actual,own.world)){
                if(own==acknowledgedPlacement)observed=actual.clone();
                healthy(now);return false;
            }
            external(actual,anchor);return true;
        }
        public boolean waiting(){return !pending.isEmpty();}
        public boolean canSend(){return pending.size()<MAX_PENDING;}
        public float[] at(float[] anchor){return WorkspaceMath.restore(anchor,relative);}
        public void sent(float[] world,long requested,long now){
            if(!canSend())throw new IllegalStateException("Window placement pipeline is full");
            pending.addLast(new Placement(world,requested,now));
        }
    }
}
