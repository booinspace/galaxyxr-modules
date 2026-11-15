package local.gxr.workspaces;

import android.os.Handler;
import android.os.SystemClock;
import java.io.Closeable;
import java.io.IOException;

/** A reusable, empty native node used only to sample a horizon-level facing reference. */
final class CpmFacing implements Closeable {
    private final Handler owner;
    private final Class<?> nodeType,updatesType,requestType;
    private Object root,node;
    private CpmLayouts.Reference reference;
    private boolean closed;
    private long pendingStamp,pendingAt,confirmedAt;
    private float[] confirmed;
    CpmFacing(CpmLayouts layouts,Handler owner)throws Exception{
        this.owner=owner;
        nodeType=Class.forName("android.graphics.CPM$Node");
        updatesType=Class.forName("android.graphics.CPM$NodeUpdates");
        requestType=Class.forName("android.graphics.CPM$TransformUpdateRequest");
        try{AndroidAccess.on(owner,()->{
            root=nodeType.getConstructor(int.class).newInstance(1);
            node=nodeType.getConstructor(int.class).newInstance(1);
            reference=layouts.new Reference(node);
            Object updates=updatesType.getConstructor().newInstance();
            try{
                set(updates,"setName",new Class<?>[]{nodeType,String.class},root,"booinspace-workspace-facing-sample");
                set(updates,"setWorldLocked",new Class<?>[]{nodeType,boolean.class},root,true);
                set(updates,"setIsXRComputer",new Class<?>[]{nodeType,boolean.class},root,true);
                set(updates,"setVisible",new Class<?>[]{nodeType,boolean.class},root,false);
                set(updates,"setParent",new Class<?>[]{nodeType,nodeType},node,root);
                set(updates,"setSpaceTransformId",new Class<?>[]{nodeType,int.class},node,0x476b00+android.os.Process.myPid());
                AndroidAccess.get(updates,"apply");
            }finally{AndroidAccess.get(updates,"close");}
            return null;
        });}catch(Exception error){try{close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void set(Object updates,String name,Class<?>[] types,Object...args)throws Exception{
        AndroidAccess.call(updates,name,types,args);
    }
    private long request()throws Exception{
        if(closed)throw new IllegalStateException("Facing tracker stopped");
        final long stamp=System.nanoTime();
        AndroidAccess.on(owner,()->{
            Object updates=updatesType.getConstructor().newInstance();
            try{
                Object request=requestType.getConstructor().newInstance();
                requestType.getField("flags").setInt(request,1|128);
                requestType.getField("coordinateSpace").setInt(request,6);
                requestType.getField("launchDistanceMeters").setFloat(request,2f);
                requestType.getField("timestamp").setLong(request,stamp);
                set(updates,"requestTransformUpdate",new Class<?>[]{nodeType,requestType},node,request);
                AndroidAccess.get(updates,"apply");
            }finally{AndroidAccess.get(updates,"close");}
            return null;
        });
        pendingStamp=stamp;pendingAt=SystemClock.uptimeMillis();return stamp;
    }
    float[] sample(long timeout)throws Exception{
        long stamp=request(),until=SystemClock.uptimeMillis()+timeout;
        while(reference.requestStamp!=stamp&&SystemClock.uptimeMillis()<until){
            if(closed)throw new IllegalStateException("Facing tracker stopped");Thread.sleep(10);
        }
        if(reference.requestStamp!=stamp)throw new java.util.concurrent.TimeoutException("Tracking reference did not update; windows were left in place");
        confirmed=WorkspaceMath.checked(reference.matrix);confirmedAt=SystemClock.uptimeMillis();pendingStamp=0;
        return confirmed.clone();
    }
    float[] poll(long now)throws Exception{
        if(closed)throw new IllegalStateException("Facing tracker stopped");
        CpmLayouts.Snapshot sample=reference.latest;
        if(pendingStamp!=0&&sample!=null&&sample.attached&&sample.stamp==pendingStamp){
            confirmed=WorkspaceMath.checked(sample.matrix);confirmedAt=now;pendingStamp=0;
        }
        // Only the empty reference waits for its callback; window animation never waits here.
        if((pendingStamp==0&&now-pendingAt>=16)||now-pendingAt>=100)request();
        return confirmed!=null&&now-confirmedAt<=250?confirmed.clone():null;
    }
    @Override public void close()throws IOException{
        if(closed)return;
        try{AndroidAccess.on(owner,()->{
            Exception failure=null;
            if(reference!=null)try{reference.close();}catch(Exception error){failure=error;}
            if(node!=null)try{AndroidAccess.get(node,"close");}catch(Exception error){failure=error;}
            if(root!=null)try{AndroidAccess.get(root,"close");}catch(Exception error){failure=error;}
            closed=true;if(failure!=null)throw failure;return null;
        });}catch(Exception error){throw new IOException("Could not close facing tracker",error);}
    }
}
