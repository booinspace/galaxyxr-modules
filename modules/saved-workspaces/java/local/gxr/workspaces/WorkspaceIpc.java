package local.gxr.workspaces;

import android.os.SystemClock;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.util.UUID;
import java.util.function.BooleanSupplier;

/** One authenticated, expiring command at a time; no shell text or externally supplied paths. */
final class WorkspaceIpc {
    static final int MAGIC=0x57535251,PREFLIGHT=0,CLOSE=1,LAUNCH=2;
    static final class Request{
        final String token,id,component,expectedBase;
        final int action,kind,task;
        final long issued;
        Request(String token,String id,long issued,int action,String component,int kind,int task,String expectedBase){
            if(token==null||!token.matches("[0-9a-f]{32}")||id==null||!id.matches("[0-9a-f-]{36}"))throw new IllegalArgumentException("Invalid workspace session");
            new Workspace.Window(component,kind,1200,800,false,WorkspaceMath.identity(),new float[]{1,0,0,0},0);
            if(action<0||action>2||task<0||expectedBase==null||expectedBase.length()>400)throw new IllegalArgumentException("Invalid workspace request");
            this.token=token;this.id=id;this.issued=issued;this.action=action;this.component=component;this.kind=kind;this.task=task;this.expectedBase=expectedBase;
        }
        void fresh()throws IOException{long age=SystemClock.uptimeMillis()-issued;if(age<0||age>30000)throw new IOException("Workspace command expired");}
    }
    private final File directory;
    private final String token;
    private final BooleanSupplier live;
    WorkspaceIpc(File directory,String token,BooleanSupplier live){this.directory=directory;this.token=token;this.live=live;}
    synchronized int call(int action,Workspace.Window window,int task,String expected)throws Exception{
        String id=UUID.randomUUID().toString();
        Request request=new Request(token,id,SystemClock.uptimeMillis(),action,window.component,window.kind,task,expected);
        WorkspaceFiles.write(new File(directory,"request.bin"),encode(request));
        long until=SystemClock.uptimeMillis()+30000;
        File response=new File("/dev/gxr_saved_workspaces/replies",token+".bin");
        while(live.getAsBoolean()&&SystemClock.uptimeMillis()<until){
            if(response.isFile()){
                try(DataInputStream input=new DataInputStream(new ByteArrayInputStream(WorkspaceFiles.read(response,8192)))){
                    if(input.readInt()!=MAGIC)throw new IOException("Invalid root response");
                    String session=input.readUTF(),nonce=input.readUTF();
                    if(session.equals(token)&&nonce.equals(id)){
                        boolean success=input.readBoolean();int result=input.readInt();String error=input.readUTF();
                        if(!success)throw new IOException(error);return result;
                    }
                }
            }
            Thread.sleep(50);
        }
        throw new IOException("Workspace root service stopped or timed out; saved layouts were preserved");
    }
    static byte[] encode(Request r)throws IOException{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(MAGIC);out.writeUTF(r.token);out.writeUTF(r.id);out.writeLong(r.issued);out.writeInt(r.action);out.writeUTF(r.component);out.writeInt(r.kind);out.writeInt(r.task);out.writeUTF(r.expectedBase);out.flush();return bytes.toByteArray();
    }
    static Request read(File file)throws IOException{
        try(DataInputStream in=new DataInputStream(new ByteArrayInputStream(WorkspaceFiles.read(file,4096)))){
            if(in.readInt()!=MAGIC)throw new IOException("Invalid root request");
            Request r=new Request(in.readUTF(),in.readUTF(),in.readLong(),in.readInt(),in.readUTF(),in.readInt(),in.readInt(),in.readUTF());
            if(in.available()!=0)throw new IOException("Trailing root request");return r;
        }catch(IllegalArgumentException invalid){throw new IOException("Invalid root request",invalid);}
    }
    static void reply(File directory,Request request,boolean success,int task,String error,int uid)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(MAGIC);out.writeUTF(request.token);out.writeUTF(request.id);out.writeBoolean(success);out.writeInt(task);out.writeUTF(error.length()>2000?error.substring(0,2000):error);out.flush();
        File temporary=new File(directory,request.token+".ready");WorkspaceFiles.write(temporary,bytes.toByteArray());
        android.system.Os.chown(temporary.getPath(),0,uid);android.system.Os.chmod(temporary.getPath(),0640);
        WorkspaceFiles.inheritContext(temporary,directory);
        java.nio.file.Files.move(temporary.toPath(),new File(directory,request.token+".bin").toPath(),
                java.nio.file.StandardCopyOption.ATOMIC_MOVE,java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    }
}
