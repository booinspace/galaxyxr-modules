package local.gxr.workspaces;

import android.app.ActivityManager.RunningTaskInfo;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

/** Exact AZJ2 reflection boundaries, kept out of the portable layout/state code. */
final class AndroidAccess {
    private AndroidAccess() {}
    static Object field(Object value,String name)throws Exception{
        for(Class<?> type=value.getClass();type!=null;type=type.getSuperclass()){
            try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(value);}
            catch(NoSuchFieldException absent){/* Look in the superclass. */}
        }
        throw new NoSuchFieldException(name);
    }
    static Object call(Object value,String name,Class<?>[] types,Object...args)throws Exception{
        for(Class<?> type=value.getClass();type!=null;type=type.getSuperclass()){
            try{Method m=type.getDeclaredMethod(name,types);m.setAccessible(true);return invoke(m,value,args);}
            catch(NoSuchMethodException absent){/* Look in the superclass. */}
        }
        throw new NoSuchMethodException(name);
    }
    static Object get(Object value,String name)throws Exception{return call(value,name,new Class<?>[0]);}
    static Object invoke(Method method,Object target,Object...args)throws Exception{
        try{return method.invoke(target,args);}catch(InvocationTargetException wrapped){
            Throwable error=wrapped.getCause();if(error instanceof Exception)throw (Exception)error;throw new IllegalStateException(error);
        }
    }
    static Object staticCall(String type,String name,Class<?>[] types,Object...args)throws Exception{
        return invoke(Class.forName(type).getMethod(name,types),null,args);
    }
    @SuppressWarnings("unchecked")
    static List<RunningTaskInfo> tasks()throws Exception{
        Object manager=staticCall("android.app.ActivityTaskManager","getInstance",new Class<?>[0]);
        return new ArrayList<>((List<RunningTaskInfo>)call(manager,"getTasks",new Class<?>[]{int.class},100));
    }
    static int mode(RunningTaskInfo info)throws Exception{return ((Number)field(info,"xrDesktopMode")).intValue();}
    static boolean visible(RunningTaskInfo info)throws Exception{return (Boolean)field(info,"isVisible")&&(Boolean)field(info,"isVisibleRequested");}
    static Rect bounds(RunningTaskInfo info)throws Exception{
        return new Rect((Rect)get(field(field(info,"configuration"),"windowConfiguration"),"getBounds"));
    }
    static boolean allowed(Context context,RunningTaskInfo info)throws Exception{
        if(((Number)field(info,"userId")).intValue()!=0||info.baseActivity==null)return false;
        String pkg=info.baseActivity.getPackageName();
        if(pkg.equals("com.android.systemui")||pkg.equals("me.weishu.kernelsu")||pkg.equals("com.samsung.android.app.xr.home"))return false;
        ApplicationInfo app=context.getPackageManager().getApplicationInfo(pkg,0);
        return app.uid>=10000;
    }
    static Intent launch(Context context,Workspace.Window state)throws Exception{
        ComponentName component=ComponentName.unflattenFromString(state.component);
        if(component==null)throw new IllegalArgumentException("Invalid workspace app");
        PackageManager pm=context.getPackageManager();
        ApplicationInfo app=pm.getApplicationInfo(component.getPackageName(),0);
        if(app.uid<10000||component.getPackageName().equals("com.android.systemui")||component.getPackageName().equals("me.weishu.kernelsu")
                ||component.getPackageName().equals("com.samsung.android.app.xr.home"))throw new IllegalArgumentException("Protected app");
        Intent launch=pm.getLaunchIntentForPackage(component.getPackageName());
        if(launch==null||!component.equals(launch.getComponent()))throw new IllegalArgumentException("The app launcher changed or is unavailable: "+component.getPackageName());
        ActivityInfo activity=pm.getActivityInfo(component,0);
        if(!activity.enabled||!activity.exported)throw new IllegalArgumentException("App launcher is unavailable");
        if(state.kind!=Workspace.Window.IMMERSIVE){
            if((((Number)field(activity,"privateFlags")).intValue()&16)!=0)throw new IllegalArgumentException("App requires immersive mode");
            PackageManager.Property mode=null;
            try{mode=pm.getProperty("android.window.PROPERTY_XR_ACTIVITY_START_MODE",component);}catch(PackageManager.NameNotFoundException absent){/* Try app. */}
            if(mode==null)try{mode=pm.getProperty("android.window.PROPERTY_XR_ACTIVITY_START_MODE",component.getPackageName());}catch(PackageManager.NameNotFoundException absent){/* Ordinary app. */}
            if(mode!=null&&mode.isString()&&mode.getString()!=null&&!mode.getString().equals("XR_ACTIVITY_START_MODE_UNDEFINED")
                    &&!mode.getString().equals("XR_ACTIVITY_START_MODE_HOME_SPACE"))throw new IllegalArgumentException("App requires its own XR mode");
        }
        return launch;
    }
    static <T>T on(Handler owner,Callable<T> action)throws Exception{
        if(owner==null)throw new IllegalStateException("Window owner is not ready");
        if(Looper.myLooper()==owner.getLooper())return action.call();
        FutureTask<T> task=new FutureTask<>(action);
        if(!owner.post(task))throw new IllegalStateException("Window owner stopped");
        try{return task.get(3,TimeUnit.SECONDS);}finally{task.cancel(false);}
    }
}
