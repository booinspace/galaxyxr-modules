package local.gxr.workspaces;

import android.content.Context;
import android.os.Handler;
import android.os.SystemClock;
import java.io.Closeable;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/** Owns same-node transform listeners and an invisible native facing reference. */
final class CpmLayouts implements Closeable {
    private static final AtomicInteger IDS=new AtomicInteger(0x475857);
    private final Object host,repository,factory,unit;
    private final Handler owner;
    private final Class<?> nodeType,updatesType,requestType,functionType;
    private final Map<Integer,Reference> references=new HashMap<>();
    private volatile boolean closed;
    CpmLayouts(Context context,Object host)throws Exception{
        this.host=host;repository=AndroidAccess.field(host,"repository");owner=(Handler)AndroidAccess.get(host,"owner");
        ClassLoader loader=context.getClassLoader();
        factory=loader.loadClass("com.android.systemui.xr.spatial.CpmNodeTransformListenerFactory").getConstructor().newInstance();
        functionType=loader.loadClass("kotlin.jvm.functions.Function1");unit=loader.loadClass("kotlin.Unit").getField("INSTANCE").get(null);
        nodeType=Class.forName("android.graphics.CPM$Node");updatesType=Class.forName("android.graphics.CPM$NodeUpdates");requestType=Class.forName("android.graphics.CPM$TransformUpdateRequest");
    }
    private void check()throws Exception{AndroidAccess.get(host,"requireLive");if(closed)throw new IllegalStateException("Workspace tracker stopped");}
    final class Reference implements Closeable{
        final Object node;
        final Object listener;
        volatile float[] matrix;
        volatile long requestStamp;
        volatile boolean disposed;
        Reference(Object borrowed)throws Exception{
            node=AndroidAccess.get(borrowed,"deepCopy");
            if(node==borrowed||!node.equals(borrowed))throw new IllegalStateException("Expected an owned same-node reference");
            Object callback=Proxy.newProxyInstance(functionType.getClassLoader(),new Class<?>[]{functionType},(proxy,method,args)->{
                if(method.getName().equals("invoke")){
                    if(!disposed){
                        Object update=args[0];
                        try{
                            if((Boolean)AndroidAccess.field(update,"attached")){
                                matrix=WorkspaceMath.checked((float[])AndroidAccess.field(update,"transform"));
                                requestStamp=((Number)AndroidAccess.field(update,"requestTimestamp")).longValue();
                            }
                        }catch(Exception invalid){matrix=null;}
                    }
                    return unit;
                }
                if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
                if(method.getName().equals("equals"))return proxy==args[0];
                return "Saved workspace transform listener";
            });
            try{listener=AndroidAccess.call(factory,"create",new Class<?>[]{nodeType,functionType},node,callback);}
            catch(Exception error){AndroidAccess.get(node,"close");throw error;}
        }
        public void close()throws java.io.IOException{
            disposed=true;
            try{try{((Closeable)listener).close();}finally{AndroidAccess.get(node,"close");}}
            catch(Exception error){throw new java.io.IOException("Could not close workspace transform listener",error);}
        }
    }
    Object subspace(int id)throws Exception{return AndroidAccess.call(repository,"getTaskSubspace",new Class<?>[]{int.class},id);}
    Reference reference(int id)throws Exception{
        return AndroidAccess.on(owner,()->{
            check();Object task=subspace(id);if(task==null)throw new IllegalStateException("Window is not attached");
            Object transform=AndroidAccess.get(task,"getNonSpatializedTransformNode");Object node=AndroidAccess.get(transform,"getNode");
            Reference old=references.get(id);
            if(old!=null&&!old.disposed&&old.node.equals(node))return old;
            if(old!=null)old.close();
            Reference created=new Reference(node);references.put(id,created);return created;
        });
    }
    float[] matrix(int id)throws Exception{
        Reference ref=reference(id);long until=SystemClock.uptimeMillis()+2500;
        while(ref.matrix==null&&SystemClock.uptimeMillis()<until){check();Thread.sleep(20);}
        if(ref.matrix==null)throw new IllegalStateException("Window position is not available yet");
        return WorkspaceMath.checked(ref.matrix);
    }
    float[] facingAnchor()throws Exception{
        final Object[] owned=new Object[2];
        final Reference[] result=new Reference[1];
        try{
            AndroidAccess.on(owner,()->{
                check();Object root=nodeType.getConstructor(int.class).newInstance(1);owned[0]=root;
                Object node=nodeType.getConstructor(int.class).newInstance(1);owned[1]=node;
                result[0]=new Reference(node);
                Object updates=updatesType.getConstructor().newInstance();
                try{
                    AndroidAccess.call(updates,"setName",new Class<?>[]{nodeType,String.class},root,"booinspace-workspace-reference");
                    AndroidAccess.call(updates,"setWorldLocked",new Class<?>[]{nodeType,boolean.class},root,true);
                    AndroidAccess.call(updates,"setIsXRComputer",new Class<?>[]{nodeType,boolean.class},root,true);
                    AndroidAccess.call(updates,"setVisible",new Class<?>[]{nodeType,boolean.class},root,false);
                    AndroidAccess.call(updates,"setParent",new Class<?>[]{nodeType,nodeType},node,root);
                    AndroidAccess.call(updates,"setSpaceTransformId",new Class<?>[]{nodeType,int.class},node,IDS.getAndIncrement());
                    Object request=requestType.getConstructor().newInstance();
                    requestType.getField("flags").setInt(request,1);
                    requestType.getField("coordinateSpace").setInt(request,6);
                    requestType.getField("launchDistanceMeters").setFloat(request,2f);
                    requestType.getField("timestamp").setLong(request,System.nanoTime());
                    AndroidAccess.call(updates,"requestTransformUpdate",new Class<?>[]{nodeType,requestType},node,request);
                    AndroidAccess.get(updates,"apply");
                }finally{AndroidAccess.get(updates,"close");}
                return null;
            });
            long until=SystemClock.uptimeMillis()+2500;
            while(result[0].matrix==null&&SystemClock.uptimeMillis()<until){check();Thread.sleep(20);}
            if(result[0].matrix==null)throw new IllegalStateException("AZJ2 did not provide the native facing reference; no apps were changed");
            float[] pose=WorkspaceMath.checked(result[0].matrix);
            long stamp=System.nanoTime();
            AndroidAccess.on(owner,()->{
                Object updates=updatesType.getConstructor().newInstance();
                try{
                    Object request=requestType.getConstructor().newInstance();
                    requestType.getField("flags").setInt(request,32);
                    requestType.getField("coordinateSpace").setInt(request,6);
                    requestType.getField("explicitMatrix").set(request,pose.clone());
                    requestType.getField("timestamp").setLong(request,stamp);
                    AndroidAccess.call(updates,"requestTransformUpdate",new Class<?>[]{nodeType,requestType},owned[1],request);
                    AndroidAccess.get(updates,"apply");
                }finally{AndroidAccess.get(updates,"close");}
                return null;
            });
            until=SystemClock.uptimeMillis()+2500;
            while(result[0].requestStamp!=stamp&&SystemClock.uptimeMillis()<until){check();Thread.sleep(20);}
            if(result[0].requestStamp!=stamp)throw new IllegalStateException("Facing-reference round trip was not acknowledged");
            float[] actual=result[0].matrix;
            for(int i=0;i<16;i++)if(Math.abs(pose[i]-actual[i])>.015f)throw new IllegalStateException("AZJ2 coordinate mapping differs; no apps were changed");
            return pose;
        }finally{
            AndroidAccess.on(owner,()->{
                Exception failure=null;
                if(result[0]!=null)try{result[0].close();}catch(Exception e){failure=e;}
                for(int i=1;i>=0;i--)if(owned[i]!=null)try{AndroidAccess.get(owned[i],"close");}catch(Exception e){failure=e;}
                if(failure!=null)throw failure;return null;
            });
        }
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    void place(int id,float[] world)throws Exception{
        WorkspaceMath.checked(world);Reference ref=reference(id);long stamp=System.nanoTime();
        AndroidAccess.on(owner,()->{
            check();Object task=subspace(id);if(task==null)throw new IllegalStateException("Window closed during restore");
            Object transform=AndroidAccess.get(task,"getNonSpatializedTransformNode");
            if(!ref.node.equals(AndroidAccess.get(transform,"getNode")))throw new IllegalStateException("Window node was replaced");
            Method request=null;
            for(Method candidate:transform.getClass().getMethods())if(candidate.getName().equals("requestUpdate")&&candidate.getParameterTypes().length==4){
                if(request!=null)throw new IllegalStateException("Ambiguous spatial transform API");request=candidate;
            }
            if(request==null)throw new NoSuchMethodException("AZJ2 requestUpdate");
            Class<?>[] types=request.getParameterTypes();
            Object explicit=transform.getClass().getClassLoader().loadClass(types[2].getName()+"$ExplicitMatrix").getConstructor(float[].class).newInstance((Object)world.clone());
            Object space=Enum.valueOf((Class)types[3],"OPENXR_UNBOUNDED");
            Object updates=updatesType.getConstructor().newInstance();
            try{AndroidAccess.invoke(request,transform,updates,stamp,explicit,space);AndroidAccess.get(updates,"apply");}
            finally{AndroidAccess.get(updates,"close");}
            return null;
        });
        long until=SystemClock.uptimeMillis()+2500;
        while(ref.requestStamp!=stamp&&SystemClock.uptimeMillis()<until){check();Thread.sleep(20);}
        if(ref.requestStamp!=stamp)throw new IllegalStateException("Window placement was not acknowledged");
    }
    void sweep(java.util.Set<Integer> live)throws Exception{
        AndroidAccess.on(owner,()->{java.util.Iterator<Map.Entry<Integer,Reference>> it=references.entrySet().iterator();
            while(it.hasNext()){Map.Entry<Integer,Reference> entry=it.next();if(!live.contains(entry.getKey())){entry.getValue().close();it.remove();}}return null;});
    }
    @Override public void close()throws java.io.IOException{
        closed=true;
        try{AndroidAccess.on(owner,()->{Exception failure=null;for(Reference ref:references.values())try{ref.close();}catch(Exception e){failure=e;}
            references.clear();if(failure!=null)throw failure;return null;});}
        catch(Exception error){throw new java.io.IOException("Workspace listener cleanup failed",error);}
    }
}
