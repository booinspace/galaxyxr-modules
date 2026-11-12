import Java from 'frida-java-bridge';

rpc.exports = {
    init() {
        const art = Process.getModuleByName('libart.so');
        const flag = art.findSymbolByName('_ZN3art15gUseUserfaultfdE');
        const allocator = art.findSymbolByName('_ZN3art7Runtime22CreateCalleeSaveMethodEv');
        if (flag === null || flag.readU8() !== 1 || allocator === null) {
            throw new Error('This test requires CMC and the tracked ART allocator');
        }
        console.log('PROBE_ART ' + JSON.stringify({pid: Process.id, cmc: flag?.readU8(),
            allocator: allocator !== null, variant: 'VARIANT'}));
        Java.performNow(() => {
            const factory = Java.ClassFactory.get(Java.use('java.lang.ClassLoader').getSystemClassLoader());
            const probe = factory.use('local.gxr.probe.CmcProbe');
            const target = factory.use('local.gxr.probe.CmcProbe$Target');
            const value = target.value.overload('boolean', 'int');
            value.implementation = function (enabled, sequence) {
                probe.hookCalls.value++;
                return value.call(this, enabled, sequence);
            };
            console.log('PROBE_HOOKED');
            probe.start.value = true;
        });
    },
};
