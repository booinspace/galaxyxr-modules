package com.gxr.wear;

import android.os.IBinder;
import android.os.Parcel;
import java.lang.reflect.Method;

/** AZJ2 physical-panel power; leaves Android's interactive state unchanged. */
public final class DisplayPower {
    private final IBinder composer;
    private final IBinder token;
    private final Method setPowerMode;

    public DisplayPower() throws Exception {
        composer = (IBinder) Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, "SurfaceFlingerAIDL");
        if (composer == null || !"android.gui.ISurfaceComposer".equals(composer.getInterfaceDescriptor())) {
            throw new IllegalStateException("Stock display composer unavailable");
        }
        // Android 14's read-only AIDL getters (6/7) were verified on pinned AZJ2.
        Parcel data = Parcel.obtain(), reply = Parcel.obtain();
        long physicalId;
        try {
            data.writeInterfaceToken("android.gui.ISurfaceComposer");
            if (!composer.transact(6, data, reply, 0)) throw new IllegalStateException("No physical display list");
            reply.readException();
            long[] ids = reply.createLongArray();
            if (ids == null || ids.length != 1 || ids[0] <= 0) {
                throw new IllegalStateException("Expected the single stock headset display");
            }
            physicalId = ids[0];
        } finally { data.recycle(); reply.recycle(); }
        data = Parcel.obtain(); reply = Parcel.obtain();
        try {
            data.writeInterfaceToken("android.gui.ISurfaceComposer");
            data.writeLong(physicalId);
            if (!composer.transact(7, data, reply, 0)) throw new IllegalStateException("No physical display token");
            reply.readException();
            token = reply.readStrongBinder();
            if (token == null) throw new IllegalStateException("Invalid physical display token");
        } finally { data.recycle(); reply.recycle(); }
        setPowerMode = Class.forName("android.view.SurfaceControl")
                .getMethod("setDisplayPowerMode", IBinder.class, int.class);
    }

    public void linkToDeath(IBinder.DeathRecipient recipient) throws Exception {
        composer.linkToDeath(recipient, 0);
    }

    public void blank(boolean blank) throws Exception {
        setPowerMode.invoke(null, token, blank ? 0 : 2);
    }
}
