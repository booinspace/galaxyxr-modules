package local.gxr.controls;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.SurfaceControl;
import android.widget.SeekBar;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Reuses the stock dimmer widget and state manager, with Java-owned callbacks and cleanup. */
public final class PassthroughBlend {
    private static final String PREFIX="com.android.systemui.xr.wm.shell.mixedreality.";
    private final Handler main=new Handler(Looper.getMainLooper());
    private final Object manager;
    private final Class<?> homeType,alphaType,pairType;
    private final Object homeAlphaType;
    private final int barId,containerId,brightnessId,mediaId;
    private final float originalAlpha;
    private final List<Binding> bindings=new ArrayList<>();
    private Panel panel;
    private volatile long heartbeat=SystemClock.uptimeMillis();
    private volatile boolean closing,stopped;
    private volatile String error="",layout="";
    private volatile int percent,panelHeight;
    public PassthroughBlend(Context context,Object dimmer)throws Exception {
        manager=field(dimmer,"mixedRealityStateManager");
        ClassLoader loader=manager.getClass().getClassLoader();
        homeType=loader.loadClass(PREFIX+"PassthroughModeState$Home");
        alphaType=loader.loadClass(PREFIX+"AlphaUpdate");
        Class<?> alphaKind=loader.loadClass(PREFIX+"AlphaUpdate$PassthroughType");
        homeAlphaType=alphaKind.getField("HOME").get(null);
        pairType=loader.loadClass("kotlin.Pair");
        Object requested=call(field(manager,"requestedModeStateStacks"),"getValue");
        originalAlpha=((Number)call(call(requested,"getThird"),"getHomePassthroughAlpha")).floatValue();
        barId=context.getResources().getIdentifier("quick_settings_dimmer_bar","id","com.android.systemui");
        containerId=context.getResources().getIdentifier("quick_settings_dimmer_bar_container","id","com.android.systemui");
        brightnessId=context.getResources().getIdentifier("quick_settings_brightness_bar_container","id","com.android.systemui");
        mediaId=context.getResources().getIdentifier("quick_settings_media_player_container","id","com.android.systemui");
        if(barId==0 || containerId==0 || brightnessId==0 || mediaId==0 || !Float.isFinite(originalAlpha) || originalAlpha<0 || originalAlpha>1)
            throw new IllegalStateException("AZJ2 passthrough controls unavailable");
        main.postDelayed(watchdog,500);
    }
    private static Object field(Object object,String name)throws Exception {
        for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass())try {
            Field member=type.getDeclaredField(name);member.setAccessible(true);return member.get(object);
        }catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(name);
    }
    private static Object call(Object object,String name,Class<?>[] types,Object...args)throws Exception {
        for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass())try {
            Method method=type.getDeclaredMethod(name,types);method.setAccessible(true);
            try{return method.invoke(object,args);}catch(InvocationTargetException wrapped){
                Throwable cause=wrapped.getCause();if(cause instanceof Exception)throw (Exception)cause;throw wrapped;
            }
        }catch(NoSuchMethodException ignored){}
        throw new NoSuchMethodException(name);
    }
    private static Object call(Object object,String name)throws Exception{return call(object,name,new Class<?>[0]);}
    private Object vrStack()throws Exception{return call(call(field(manager,"requestedModeStateStacks"),"getValue"),"getFirst");}
    private Object currentPt()throws Exception{return call(call(manager,"getComputedPassthroughModeState"),"getValue");}
    private static String kind(Object value){return value.getClass().getSimpleName();}
    private boolean live(){long age=SystemClock.uptimeMillis()-heartbeat;return !closing && age>=0 && age<=5000;}
    public void pulse(){heartbeat=SystemClock.uptimeMillis();}
    /** Change only the Home/background pair after the stock priority and safety checks have run. */
    public Object states(Object stack,Object pair)throws Exception {
        if(!live())return pair;
        Object pt=call(pair,"getSecond"),vr=call(stack,"getHighestPriorityState");
        float alpha=((Number)call(pt,"getComputedAlpha")).floatValue();
        if(!PassthroughBlendPolicy.blend(kind(pt),kind(vr),alpha))return pair;
        return pairType.getConstructor(Object.class,Object.class).newInstance(vr,pt);
    }
    public void attach(View root,Object xrView) {
        if(closing || root==null)return;
        main.post(()->{
            if(!live())return;
            try {
                for(Binding old:bindings)if(old.root==root)return;
                if(bindings.size()>=8)throw new IllegalStateException("Too many Quick Settings roots");
                if(panel==null)panel=new Panel(xrView);
                if(panel.xr!=xrView)throw new IllegalStateException("Unexpected Quick Settings panel owner");
                bindings.add(new Binding(root));
            }catch(Exception failure){fail(failure);}
        });
    }
    public void detach(View root){main.post(()->bindings.removeIf(binding->{
        if(binding.root!=root)return false;binding.restore();return true;
    }));}
    private void apply(int progress,int minimum,int maximum)throws Exception {
        if(!live())return;
        Object requestedVr=call(vrStack(),"getHighestPriorityState"),pt=currentPt();
        if(!PassthroughBlendPolicy.adjustable(kind(pt),kind(requestedVr)))return;
        float alpha=PassthroughBlendPolicy.alpha(progress,minimum,maximum);
        Object home=homeType.getConstructor(boolean.class,Float.class,boolean.class).newInstance(alpha>0,null,false);
        Class<?> alphaKind=homeAlphaType.getClass();
        Object update=alphaType.getConstructor(alphaKind,float.class).newInstance(homeAlphaType,alpha);
        call(manager,"setModeStatesAtomic",new Class<?>[]{List.class,List.class,List.class},
                Collections.emptyList(),Collections.singletonList(home),Collections.singletonList(update));
        percent=Math.round(alpha*100);
    }
    private static ViewGroup.LayoutParams anchored(View view,String name,int target)throws Exception {
        ViewGroup.LayoutParams original=view.getLayoutParams();Class<?> type=original.getClass();
        ViewGroup.LayoutParams copy=(ViewGroup.LayoutParams)type.getConstructor(ViewGroup.LayoutParams.class).newInstance(original);
        type.getField(name).setInt(copy,target);return copy;
    }
    private final class Binding {
        final View root,container,brightness,media;
        final ViewGroup.LayoutParams originalRow,originalMedia,blendRow,blendMedia;
        final SeekBar bar;
        final SeekBar.OnSeekBarChangeListener originalListener;
        final int barVisibility,containerVisibility;
        final boolean enabled;
        final CharSequence description;
        Binding(View root)throws Exception {
            this.root=root;bar=(SeekBar)root.findViewById(barId);container=root.findViewById(containerId);
            brightness=root.findViewById(brightnessId);
            media=root.findViewById(mediaId);
            if(bar==null || container==null || brightness==null || media==null)throw new IllegalStateException("Native passthrough slider missing");
            originalRow=container.getLayoutParams();originalMedia=media.getLayoutParams();
            // Samsung anchors media to brightness, bypassing its normally hidden dimmer row.
            blendRow=anchored(container,"bottomToTop",-1);blendMedia=anchored(media,"topToBottom",containerId);
            originalListener=(SeekBar.OnSeekBarChangeListener)field(bar,"seekbarChangeListener");
            barVisibility=bar.getVisibility();containerVisibility=container.getVisibility();description=bar.getContentDescription();enabled=bar.isEnabled();
            try {
            container.setLayoutParams(blendRow);media.setLayoutParams(blendMedia);
            bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
                public void onStartTrackingTouch(SeekBar ignored){}
                public void onStopTrackingTouch(SeekBar ignored){}
                public void onProgressChanged(SeekBar view,int value,boolean fromUser){
                    if(!fromUser)return;
                    try{apply(value,bar.getMin(),bar.getMax());}catch(Exception failure){fail(failure);}
                }
            });
            bar.setContentDescription("Passthrough blend");
            refresh();
            }catch(Exception failure){restore();throw failure;}
        }
        void refresh()throws Exception {
            Object pt=currentPt(),vr=call(vrStack(),"getHighestPriorityState");
            boolean allowed=PassthroughBlendPolicy.adjustable(kind(pt),kind(vr));
            float alpha=((Number)call(pt,"getComputedAlpha")).floatValue();
            if(!Float.isFinite(alpha) || alpha<0 || alpha>1)throw new IllegalStateException("Invalid passthrough alpha");
            bar.setEnabled(allowed);bar.setProgress(Math.round(bar.getMin()+(bar.getMax()-bar.getMin())*alpha));
            percent=Math.round(alpha*100);
            if(brightness.getVisibility()!=View.VISIBLE){container.setVisibility(View.GONE);bar.setVisibility(View.GONE);}
            else if(panel.room(root,container)){container.setVisibility(View.VISIBLE);bar.setVisibility(View.VISIBLE);}
            layout="root="+root.getWidth()+"x"+root.getHeight()+", row="+container.getTop()+".."+container.getBottom()
                    +", media="+media.getTop()+".."+media.getBottom();
        }
        void restore(){
            bar.setOnSeekBarChangeListener(originalListener);bar.setContentDescription(description);
            bar.setEnabled(enabled);bar.setVisibility(barVisibility);container.setVisibility(containerVisibility);
            if(container.getLayoutParams()==blendRow)container.setLayoutParams(originalRow);
            if(media.getLayoutParams()==blendMedia)media.setLayoutParams(originalMedia);
        }
    }
    /** Reserve a full native row in the window, crop and XR visible bounds together. */
    private final class Panel {
        final Object xr,originalHeight,metrics;
        final Field heightField;
        final Class<?> dpType;
        Object appliedHeight;
        Panel(Object xr)throws Exception {
            this.xr=xr;heightField=xr.getClass().getDeclaredField("height");heightField.setAccessible(true);
            originalHeight=heightField.get(xr);dpType=originalHeight.getClass();
            metrics=xr.getClass().getClassLoader().loadClass("com.android.systemui.xr.ui.DisplayMetrics").getField("INSTANCE").get(null);
        }
        int pixels(Object dp)throws Exception{return ((Number)call(metrics,"toPx",new Class<?>[]{dpType},dp)).intValue();}
        boolean room(View root,View row)throws Exception {
            if(root!=call(xr,"getContentView") || !root.isAttachedToWindow()
                    || !(root.getLayoutParams() instanceof WindowManager.LayoutParams))return false;
            ViewGroup.LayoutParams rowParams=row.getLayoutParams();
            int extra=rowParams.height;
            if(rowParams instanceof ViewGroup.MarginLayoutParams){
                ViewGroup.MarginLayoutParams margins=(ViewGroup.MarginLayoutParams)rowParams;
                extra+=margins.topMargin+margins.bottomMargin;
            }
            float density=((Number)field(metrics,"pxPerDp")).floatValue();
            float base=((Number)call(originalHeight,"getValue")).floatValue();
            if(extra<=0 || !Float.isFinite(density) || density<=0 || !Float.isFinite(base) || base<=0)
                throw new IllegalStateException("Invalid native Quick Settings row size");
            Object target=dpType.getConstructor(float.class).newInstance(base+extra/density);
            WindowManager.LayoutParams current=(WindowManager.LayoutParams)root.getLayoutParams();
            if(appliedHeight!=null && heightField.get(xr)==appliedHeight && current.height==pixels(target))return true;
            appliedHeight=target;heightField.set(xr,target);
            return resize(root,pixels(target));
        }
        boolean resize(View root,int height)throws Exception {
            Object retriever=field(xr,"surfaceControlRetriever"),host=field(retriever,"viewHost");
            if(host==null)return false;
            Object surfacePackage=call(host,"getSurfacePackage");
            if(surfacePackage==null)return false;
            try{
                Object surface=call(surfacePackage,"getSurfaceControl");
                if(surface==null || !Boolean.TRUE.equals(call(surface,"isValid")))return false;
                WindowManager.LayoutParams current=(WindowManager.LayoutParams)root.getLayoutParams();
                if(current.width<=0 || height<=0)throw new IllegalStateException("Invalid Quick Settings window bounds");
                WindowManager.LayoutParams updated=new WindowManager.LayoutParams();updated.copyFrom(current);updated.height=height;
                root.setLayoutParams(updated);
                call(retriever,"relayout",new Class<?>[]{WindowManager.LayoutParams.class},updated);
                call(xr,"cropWindow",new Class<?>[]{SurfaceControl.class,int.class,int.class},surface,updated.width,height);
                call(xr,"handleVisibleSizeChanged",new Class<?>[]{int.class,int.class},updated.width,height);
                panelHeight=height;return true;
            }finally{call(surfacePackage,"release");}
        }
        void restore()throws Exception {
            if(appliedHeight==null || heightField.get(xr)!=appliedHeight)return;
            heightField.set(xr,originalHeight);appliedHeight=null;
            Object root=call(xr,"getContentView");
            if(root instanceof View && ((View)root).isAttachedToWindow()
                    && ((View)root).getLayoutParams() instanceof WindowManager.LayoutParams)
                resize((View)root,pixels(originalHeight));
        }
    }
    private final Runnable watchdog=new Runnable(){public void run(){
        if(stopped)return;
        if(!live()){close();return;}
        try{for(Binding binding:bindings)binding.refresh();}
        catch(Exception failure){fail(failure);return;}
        main.postDelayed(this,500);
    }};
    private void fail(Exception failure){error=failure.toString();Log.e("GxrPassthroughBlend",error,failure);close();}
    public void close(){
        if(closing)return;closing=true;
        main.post(()->{
            main.removeCallbacks(watchdog);
            try{
                for(Binding binding:bindings)binding.restore();
            }catch(Exception failure){error=failure.toString();Log.e("GxrPassthroughBlend",error,failure);}
            finally{
                bindings.clear();
                try{if(panel!=null)panel.restore();}
                catch(Exception failure){error=failure.toString();Log.e("GxrPassthroughBlend",error,failure);}
                try{
                    Object update=alphaType.getConstructor(homeAlphaType.getClass(),float.class).newInstance(homeAlphaType,originalAlpha);
                    call(manager,"setAlpha",new Class<?>[]{alphaType},update);
                }catch(Exception failure){error=failure.toString();Log.e("GxrPassthroughBlend",error,failure);}
                stopped=true;
            }
        });
    }
    public boolean isStopped(){return stopped;}
    public String getError(){return error;}
    public int getPercent(){return percent;}
    public int getPanelHeightPx(){return panelHeight;}
    public String getLayout(){return layout;}
}
