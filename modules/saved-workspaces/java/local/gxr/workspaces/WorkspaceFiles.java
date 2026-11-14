package local.gxr.workspaces;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;

/** Private, bounded messages and thumbnails live outside the installed module tree. */
final class WorkspaceFiles {
    private WorkspaceFiles(){}
    static byte[] read(File file,int limit)throws IOException{
        // Validate the opened descriptor so a replaced path cannot turn a bounded read into a pipe.
        try{
            java.io.FileDescriptor fd=android.system.Os.open(file.getPath(),android.system.OsConstants.O_RDONLY
                    |android.system.OsConstants.O_NOFOLLOW|android.system.OsConstants.O_NONBLOCK,0);
            try{
                android.system.StructStat stat=android.system.Os.fstat(fd);
                if(!android.system.OsConstants.S_ISREG(stat.st_mode)||stat.st_size<0||stat.st_size>limit)throw new IOException("Invalid workspace file");
                java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] chunk=new byte[Math.min(limit+1,8192)];
                int size;while((size=android.system.Os.read(fd,chunk,0,chunk.length))>0){
                    if(out.size()+size>limit)throw new IOException("Workspace file grew beyond its limit");out.write(chunk,0,size);
                }
                return out.toByteArray();
            }finally{android.system.Os.close(fd);}
        }catch(android.system.ErrnoException error){throw new IOException("Cannot read workspace file",error);}
    }
    static void inheritContext(File file,File parent)throws Exception{
        Class<?> selinux=Class.forName("android.os.SELinux");
        String label=(String)selinux.getMethod("getFileContext",String.class).invoke(null,parent.getPath());
        if(label==null||!Boolean.TRUE.equals(selinux.getMethod("setFileContext",String.class,String.class).invoke(null,file.getPath(),label)))
            throw new IOException("Cannot give SystemUI access to the root response");
    }
    static void write(File file,byte[] data)throws IOException{
        File temporary=new File(file.getPath()+".new");
        if(Files.isSymbolicLink(file.toPath())||Files.isSymbolicLink(temporary.toPath()))throw new IOException("Invalid workspace file");
        try{
            try(FileOutputStream stream=new FileOutputStream(temporary)){stream.write(data);stream.getFD().sync();}
            temporary.setReadable(false,false);temporary.setWritable(false,false);
            if(!temporary.setReadable(true,true)||!temporary.setWritable(true,true))throw new IOException("Cannot protect workspace file");
            Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        }finally{Files.deleteIfExists(temporary.toPath());}
    }
}
