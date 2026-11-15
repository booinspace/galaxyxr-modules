"""Exercise the real passthrough widget/controller against small platform transport doubles."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
'android/os/Looper.java':'''package android.os;
public final class Looper {public static Looper getMainLooper(){return new Looper();}}
''',
'android/os/SystemClock.java':'''package android.os;
public final class SystemClock {public static long now;public static long uptimeMillis(){return now;}}
''',
'android/os/Handler.java':'''package android.os;
import java.util.*;
public final class Handler {
 static final List<Item> queue=new ArrayList<>();
 static final class Item {Runnable r;long time;Item(Runnable r,long time){this.r=r;this.time=time;}}
 public Handler(Looper ignored){}
 public boolean post(Runnable r){return postDelayed(r,0);}
 public boolean postDelayed(Runnable r,long delay){queue.add(new Item(r,SystemClock.now+delay));return true;}
 public void removeCallbacks(Runnable r){queue.removeIf(i->i.r==r);}
 public static void run(){for(int n=0;n<100;n++){Item found=null;for(Item i:queue)if(i.time<=SystemClock.now){found=i;break;}
  if(found==null)return;queue.remove(found);found.r.run();}throw new AssertionError("Unbounded UI queue");}
}
''',
'android/content/res/Resources.java':'''package android.content.res;
public final class Resources {public int getIdentifier(String name,String kind,String pkg){return name.contains("media_player")?4:name.contains("brightness")?3:name.endsWith("container")?2:1;}}
''',
'android/content/Context.java':'''package android.content;
public final class Context {public android.content.res.Resources getResources(){return new android.content.res.Resources();}}
''',
'android/util/Log.java':'''package android.util;
public final class Log {public static int e(String tag,String message,Throwable error){return 0;}}
''',
'android/view/View.java':'''package android.view;
import java.util.*;
public class View {
 public static final int VISIBLE=0,GONE=8;public int visibility=8;public boolean enabled=false;
 public CharSequence description="stock";public Map<Integer,View> children=new HashMap<>();
 public ViewGroup.LayoutParams params=new ViewGroup.MarginLayoutParams(0,0);public boolean attached=true;
 public ViewGroup.LayoutParams getLayoutParams(){return params;}public void setLayoutParams(ViewGroup.LayoutParams p){params=p;}
 public boolean isAttachedToWindow(){return attached;}
 public int getTop(){return 0;}public int getBottom(){return params.height;}
 public int getWidth(){return params.width;}public int getHeight(){return params.height;}
 public View findViewById(int id){return children.get(id);}
 public void setVisibility(int v){visibility=v;}public int getVisibility(){return visibility;}
 public void setEnabled(boolean v){enabled=v;}public boolean isEnabled(){return enabled;}
 public void setContentDescription(CharSequence v){description=v;}public CharSequence getContentDescription(){return description;}
}
''',
'android/view/ViewGroup.java':'''package android.view;
public class ViewGroup extends View {
 public static class LayoutParams {public int width,height;public LayoutParams(int w,int h){width=w;height=h;}}
 public static class MarginLayoutParams extends LayoutParams {public int topMargin,bottomMargin;public MarginLayoutParams(int w,int h){super(w,h);}}
}
''',
'android/view/WindowManager.java':'''package android.view;
public interface WindowManager {
 public static class LayoutParams extends ViewGroup.LayoutParams {
  public int flags;public LayoutParams(){super(500,850);flags=0x2080018;}
  public int copyFrom(LayoutParams p){width=p.width;height=p.height;flags=p.flags;return 0;}
 }
}
''',
'android/view/SurfaceControl.java':'''package android.view;
public final class SurfaceControl {public boolean isValid(){return true;}}
''',
'com/android/systemui/xr/ui/unit/Dp.java':'''package com.android.systemui.xr.ui.unit;
public final class Dp {private final float value;public Dp(float v){value=v;}public float getValue(){return value;}}
''',
'com/android/systemui/xr/ui/DisplayMetrics.java':'''package com.android.systemui.xr.ui;
import com.android.systemui.xr.ui.unit.Dp;
public final class DisplayMetrics {public static final DisplayMetrics INSTANCE=new DisplayMetrics();
 public static float pxPerDp=1;public int toPx(Dp v){return (int)(v.getValue()*pxPerDp);}}
''',
'android/widget/SeekBar.java':'''package android.widget;
public final class SeekBar extends android.view.View {
 public interface OnSeekBarChangeListener {void onStartTrackingTouch(SeekBar v);void onStopTrackingTouch(SeekBar v);void onProgressChanged(SeekBar v,int p,boolean user);}
 public final OnSeekBarChangeListener seekbarChangeListener=new OnSeekBarChangeListener(){
  public void onStartTrackingTouch(SeekBar v){}public void onStopTrackingTouch(SeekBar v){}public void onProgressChanged(SeekBar v,int p,boolean u){}
 };
 public OnSeekBarChangeListener listener=seekbarChangeListener;public int progress;
 public int getMin(){return 0;}public int getMax(){return 100;}
 public void setOnSeekBarChangeListener(OnSeekBarChangeListener v){listener=v;}
 public void setProgress(int v){progress=v;listener.onProgressChanged(this,v,false);}
 public void user(int v){progress=v;listener.onProgressChanged(this,v,true);}
}
''',
'kotlin/Pair.java':'''package kotlin;
public final class Pair {public Object first,second;public Pair(Object a,Object b){first=a;second=b;}
 public Object getFirst(){return first;}public Object getSecond(){return second;}}
''',
'com/android/systemui/xr/wm/shell/mixedreality/PassthroughModeState.java':'''package com.android.systemui.xr.wm.shell.mixedreality;
public abstract class PassthroughModeState {
 public float alpha;public float getComputedAlpha(){return alpha;}
 public static final class Home extends PassthroughModeState {public boolean enabled;
  public Home(boolean enabled,Float alpha,boolean overridden){this.enabled=enabled;this.alpha=alpha==null?1:alpha;}}
 public static final class Disabled extends PassthroughModeState {}
 public static final class Emergency extends PassthroughModeState {}
}
''',
'com/android/systemui/xr/wm/shell/mixedreality/AlphaUpdate.java':'''package com.android.systemui.xr.wm.shell.mixedreality;
public final class AlphaUpdate {public enum PassthroughType {HOME}public float alpha;
 public AlphaUpdate(PassthroughType type,float alpha){this.alpha=alpha;}}
''',
'local/gxr/controls/PassthroughBlendHostTest.java':'''package local.gxr.controls;
import android.content.Context;import android.os.*;import android.view.*;import android.widget.SeekBar;
import com.android.systemui.xr.ui.unit.Dp;import com.android.systemui.xr.ui.DisplayMetrics;
import com.android.systemui.xr.wm.shell.mixedreality.*;import kotlin.Pair;import java.util.*;
public final class PassthroughBlendHostTest {
 public static final class Flow {Object value;Flow(Object v){value=v;}public Object getValue(){return value;}}
 public static final class HomeSpaceFlinger {}public static final class AppOpenXr {}
 public static final class Stack {Object vr=new HomeSpaceFlinger();public Object getHighestPriorityState(){return vr;}}
 public static final class Alphas {float home=.4f;public float getHomePassthroughAlpha(){return home;}}
 public static final class Triple {Stack stack=new Stack();Alphas alphas=new Alphas();public Object getFirst(){return stack;}public Object getThird(){return alphas;}}
 public static final class Manager {
  Triple triple=new Triple();public Flow requestedModeStateStacks=new Flow(triple);
  Flow current=new Flow(new PassthroughModeState.Disabled());int writes;
  public Object getComputedPassthroughModeState(){return current;}
  public void setModeStatesAtomic(List<?> vr,List<?> pt,List<?> updates){
   for(Object newVr:vr)triple.stack.vr=newVr;
   writes++;PassthroughModeState.Home h=(PassthroughModeState.Home)pt.get(0);
   triple.alphas.home=((AlphaUpdate)updates.get(0)).alpha;h.alpha=triple.alphas.home;
   current.value=h.enabled?h:new PassthroughModeState.Disabled();
  }
  public void setAlpha(AlphaUpdate update){triple.alphas.home=update.alpha;}
 }
 public static final class Dimmer {public Manager mixedRealityStateManager=new Manager();}
 public static final class SurfacePackage {static int releases;SurfaceControl surface=new SurfaceControl();public Object getSurfaceControl(){return surface;}public void release(){releases++;}}
 public static final class Host {public Object getSurfacePackage(){return new SurfacePackage();}}
 public static final class Retriever {
  final Xr xr;public Host viewHost=new Host();int layouts;
  Retriever(Xr xr){this.xr=xr;}public void relayout(WindowManager.LayoutParams p){layouts++;}
 }
 public static final class Xr {
  public Dp height=new Dp(850);public Retriever surfaceControlRetriever=new Retriever(this);
  View root;int cropHeight=850,visibleHeight=850;
  Xr(View root){this.root=root;root.setLayoutParams(new WindowManager.LayoutParams());}
  public View getContentView(){return root;}
  public void cropWindow(SurfaceControl s,int width,int height){check(width==500);cropHeight=height;}
  public void handleVisibleSizeChanged(int width,int height){check(width==500);visibleHeight=height;}
 }
 public static final class Constraints extends ViewGroup.MarginLayoutParams {
  public int topToBottom=-1,bottomToTop=-1;
  public Constraints(int width,int height){super(width,height);}
  public Constraints(ViewGroup.LayoutParams source){super(source.width,source.height);Constraints p=(Constraints)source;topMargin=p.topMargin;bottomMargin=p.bottomMargin;
   topToBottom=p.topToBottom;bottomToTop=p.bottomToTop;}
 }
 private static View root(SeekBar bar,View container){
  View v=new View();v.children.put(1,bar);v.children.put(2,container);
  View brightness=new View();brightness.setVisibility(0);v.children.put(3,brightness);
  Constraints p=new Constraints(500,80);p.topMargin=14;p.topToBottom=3;p.bottomToTop=4;container.setLayoutParams(p);
  View media=new View();Constraints m=new Constraints(500,200);m.topMargin=8;m.topToBottom=3;media.setLayoutParams(m);v.children.put(4,media);return v;
 }
 private static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  Dimmer dimmer=new Dimmer();Manager manager=dimmer.mixedRealityStateManager;
  PassthroughBlend blend=new PassthroughBlend(new Context(),dimmer);
  View container=new View();SeekBar bar=new SeekBar();View root=root(bar,container);Xr xr=new Xr(root);
  ViewGroup.LayoutParams stockRow=container.params,stockMedia=root.children.get(4).params;
  blend.attach(root,xr);Handler.run();check(bar.visibility==0&&container.visibility==0&&bar.enabled);
  check(((Constraints)container.params).bottomToTop==-1&&((Constraints)root.children.get(4).params).topToBottom==2);
  check(((Constraints)stockRow).bottomToTop==4&&((Constraints)stockMedia).topToBottom==3);
  check(((Constraints)container.params).topMargin==14&&((Constraints)root.children.get(4).params).topMargin==8);
  check(xr.height.getValue()==944&&root.params.height==944&&xr.cropHeight==944&&xr.visibleHeight==944);
  check(((WindowManager.LayoutParams)root.params).flags==0x2080018);check(SurfacePackage.releases==1);
  int layouts=xr.surfaceControlRetriever.layouts;blend.attach(root,xr);Handler.run();check(xr.surfaceControlRetriever.layouts==layouts);
  root.children.get(3).setVisibility(8);SystemClock.now+=500;blend.pulse();Handler.run();
  check(bar.visibility==8&&container.visibility==8);
  root.children.get(3).setVisibility(0);SystemClock.now+=500;blend.pulse();Handler.run();
  check(bar.visibility==0&&container.visibility==0&&root.params.height==944);
  check(bar.progress==0&&manager.writes==0);bar.setProgress(70);check(manager.writes==0);
  bar.user(50);check(manager.writes==1&&manager.triple.alphas.home==.5f);
  Object pt=manager.current.value;Pair original=new Pair(new Object(),pt);
  Pair mixed=(Pair)blend.states(manager.triple.stack,original);
  check(mixed.first==manager.triple.stack.vr&&mixed.second==pt);
  SystemClock.now+=500;blend.pulse();Handler.run();check(bar.progress==50&&manager.writes==1);
  manager.current.value=new PassthroughModeState.Emergency();bar.user(20);check(manager.writes==1);
  Pair critical=new Pair(new Object(),manager.current.value);check(blend.states(manager.triple.stack,critical)==critical);
  manager.current.value=pt;manager.triple.stack.vr=new AppOpenXr();bar.user(20);check(manager.writes==1);
  check(blend.states(manager.triple.stack,original)==original);
  manager.triple.stack.vr=new HomeSpaceFlinger();bar.user(0);check(manager.current.value instanceof PassthroughModeState.Disabled);
  bar.user(100);check(((PassthroughModeState)manager.current.value).alpha==1);
  check(blend.states(manager.triple.stack,new Pair(new Object(),manager.current.value)).getClass()==Pair.class);
  blend.detach(root);Handler.run();check(bar.listener==bar.seekbarChangeListener);
  check(container.params==stockRow&&root.children.get(4).params==stockMedia);
  blend.attach(root,xr);Handler.run();check(root.params.height==944&&xr.height.getValue()==944);
  blend.close();Handler.run();check(blend.isStopped()&&blend.getError().isEmpty());
  check(root.params.height==850&&xr.height.getValue()==850&&xr.cropHeight==850&&xr.visibleHeight==850);
  check(SurfacePackage.releases==2);
  check(bar.visibility==8&&container.visibility==8&&!bar.enabled&&bar.description.equals("stock"));
  check(bar.listener==bar.seekbarChangeListener&&manager.triple.alphas.home==.4f);
  check(container.params==stockRow&&root.children.get(4).params==stockMedia);
  int writes=manager.writes;bar.user(20);check(manager.writes==writes);
  PassthroughBlend expired=new PassthroughBlend(new Context(),dimmer);expired.attach(root,xr);Handler.run();
  SystemClock.now+=5001;Handler.run();check(expired.isStopped()&&bar.listener==bar.seekbarChangeListener);
  PassthroughBlend failed=new PassthroughBlend(new Context(),dimmer);
  ((PassthroughModeState)manager.current.value).alpha=Float.NaN;
  failed.attach(root,xr);Handler.run();check(failed.isStopped()&&!failed.getError().isEmpty());
  check(bar.listener==bar.seekbarChangeListener&&bar.visibility==8);
  check(root.params.height==850&&xr.height.getValue()==850);
  // Native root reinflation keeps one extra row, including non-unit display density.
  DisplayMetrics.pxPerDp=2;((PassthroughModeState)manager.current.value).alpha=1;
  PassthroughBlend replacement=new PassthroughBlend(new Context(),dimmer);
  SeekBar firstBar=new SeekBar();View firstRow=new View(),firstRoot=root(firstBar,firstRow);Xr owner=new Xr(firstRoot);
  firstRoot.params.height=1700;firstRow.params.height=160;((ViewGroup.MarginLayoutParams)firstRow.params).topMargin=28;
  replacement.attach(firstRoot,owner);Handler.run();check(firstRoot.params.height==1888);
  replacement.detach(firstRoot);Handler.run();
  SeekBar nextBar=new SeekBar();View nextRow=new View(),nextRoot=root(nextBar,nextRow);owner.root=nextRoot;
  nextRoot.setLayoutParams(new WindowManager.LayoutParams());nextRoot.params.height=1888;
  nextRow.params.height=160;((ViewGroup.MarginLayoutParams)nextRow.params).topMargin=28;
  replacement.attach(nextRoot,owner);Handler.run();check(nextRoot.params.height==1888&&owner.height.getValue()==944);
  replacement.close();Handler.run();check(nextRoot.params.height==1700&&owner.height.getValue()==850);
  System.out.println("PASS: Samsung media anchors and exact layout rollback, non-null update lists, native row/window/crop bounds, root reinflation, user-only writes, Home blending, critical/app isolation, endpoints, lease expiry and rollback");
 }
}
''',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java',type=Path,required=True)
    parser.add_argument('--ecj',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gxr-passthrough-host-') as temporary:
        work=Path(temporary);paths=[]
        for name,body in SOURCES.items():
            path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body);paths.append(path)
        production=ROOT/'modules/quick-settings-gesture/android/local/gxr/controls'
        paths += [production/name for name in ['PassthroughBlend.java','PassthroughBlendPolicy.java']]
        paths.append(ROOT/'tests/PassthroughBlendPolicyTest.java')
        classes=work/'classes'
        subprocess.run([str(args.java),'-jar',str(args.ecj),'-source','1.8','-target','1.8','-proc:none','-d',str(classes),*map(str,paths)],check=True)
        for name in ['PassthroughBlendHostTest','PassthroughBlendPolicyTest']:
            subprocess.run([str(args.java),'-cp',str(classes),'local.gxr.controls.'+name],check=True)


if __name__=='__main__':main()
