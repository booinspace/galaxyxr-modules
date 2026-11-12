"""Check Frida's real struct-return ABI in a disposable process, never SystemUI."""
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

import frida

CPP = r'''
#include <cstdint>
#include <cstddef>
#include <vector>
#include <optional>
#include <unistd.h>
struct Handle { std::uint32_t entity; std::uint32_t padding; void* context; };
// AZJ2 libc++ returns pointer then length; host libstdc++ uses the opposite layout.
struct TargetStringView { const char* data; std::size_t length; };
struct Point3 { float x; float y; float z; };
struct Matrix { float values[16]; };
extern "C" __attribute__((visibility("default"))) Handle handle_value() {
    return {42, 0xff00ff00, reinterpret_cast<void*>(0x12345678)};
}
extern "C" __attribute__((visibility("default"))) std::vector<Handle> child_values() {
    return {{1, 0, reinterpret_cast<void*>(0x12345678)},
            {2, 0, reinterpret_cast<void*>(0x12345678)}};
}
extern "C" __attribute__((visibility("default"))) TargetStringView name_value() {
    return {"space-transform-task-42", 23};
}
extern "C" __attribute__((visibility("default"))) Point3 transform_point(const Point3* value) {
    return {value->x * 2 + 1, value->y * 3 - 2, value->z * 4 + 3};
}
extern "C" __attribute__((visibility("default"), noinline)) int resize_frame(
        void*, const void*, const void*, Handle node, const void*, const void*, std::optional<Matrix> frame) {
    return node.entity == 42 && frame ? static_cast<int>(frame->values[0]) : -1;
}
extern "C" __attribute__((visibility("default"))) int call_resize_frame() {
    Matrix matrix{};
    matrix.values[0] = 2;
    return resize_frame(nullptr, nullptr, nullptr, handle_value(), nullptr, nullptr, matrix) * 10
        + static_cast<int>(matrix.values[0]);
}
extern "C" __attribute__((visibility("default"))) void release_values(void* value) {
    ::operator delete(value);
}
int main() { while (true) pause(); }
'''
JS = r'''
const module = Module.load(LIBRARY_PATH);
const call = (name, result, args = []) => new NativeFunction(module.getExportByName(name), result, args);
const handle = call('handle_value', ['uint64', 'pointer'])();
const [begin, end, capacity] = call('child_values', ['pointer', 'pointer', 'pointer'])();
const [text, length] = call('name_value', ['pointer', 'ulong'])();
const point = Memory.alloc(12);
[.25, -.5, 2].forEach((v, i) => point.add(i * 4).writeFloat(v));
const transformed = call('transform_point', ['float', 'float', 'float'], ['pointer'])(point);
let frameHook = null;
if (Process.arch === 'arm64') {
    frameHook = Interceptor.attach(module.getExportByName('resize_frame'), {onEnter(args) {
        if (args[3].toUInt32() !== 42 || args[4].toString() !== '0x12345678' || args[7].add(64).readU8() !== 1) {
            throw new Error('Unexpected ARM64 resize argument layout');
        }
        this.frame = Memory.alloc(80);
        Memory.copy(this.frame, args[7], 65);
        this.frame.writeFloat(3);
        args[7] = this.frame;
    }});
}
const matrixArgument = call('call_resize_frame', 'int')();
if (frameHook !== null) frameHook.detach();
const result = {entity: parseInt(handle[0].toString(16).slice(-8), 16),
    context: handle[1].toString(), bytes: Number(end.sub(begin).toString()),
    capacity: Number(capacity.sub(begin).toString()), first: begin.readU32(),
    second: begin.add(16).readU32(), name: text.readUtf8String(Number(length)), transformed, matrixArgument};
call('release_values', 'void', ['pointer'])(begin);
send(result);
'''


def main():
    compiler = shutil.which('clang++') or shutil.which('c++')
    assert compiler, 'C++ compiler required for the native ABI check'
    with tempfile.TemporaryDirectory(prefix='gxr-boundary-abi-') as temporary:
        root = Path(temporary)
        (root / 'fixture.cpp').write_text(CPP)
        binary = root / 'fixture'
        library = root / ('fixture.dylib' if sys.platform == 'darwin' else 'fixture.so')
        subprocess.run([compiler, '-std=c++17', '-Wno-return-type-c-linkage', '-rdynamic',
                        str(root / 'fixture.cpp'), '-o', str(binary)], check=True)
        subprocess.run([compiler, '-std=c++17', '-Wno-return-type-c-linkage', '-fPIC',
                        '-dynamiclib' if sys.platform == 'darwin' else '-shared',
                        str(root / 'fixture.cpp'), '-o', str(library)], check=True)
        device = frida.get_local_device()
        pid = device.spawn([str(binary)])
        session = None
        messages = []
        completed = threading.Event()
        try:
            session = device.attach(pid)
            script = session.create_script(JS.replace('LIBRARY_PATH', json.dumps(str(library))))
            def receive(message, _data):
                messages.append(message)
                completed.set()
            script.on('message', receive)
            script.load()
            assert completed.wait(10), 'No native ABI result'
            assert messages[0]['type'] == 'send', json.dumps(messages)
            result = messages[0]['payload']
            assert result == {'entity': 42, 'context': '0x12345678', 'bytes': 32,
                              'capacity': 32, 'first': 1, 'second': 2,
                              'name': 'space-transform-task-42', 'transformed': [1.5, -3.5, 11],
                              'matrixArgument': 32 if platform.machine() in ('arm64', 'aarch64') else 22}, result
            script.unload()
            print('PASS: real Frida struct returns and allocator cleanup; ARM64 optional-matrix argument copy' if
                  platform.machine() in ('arm64', 'aarch64') else
                  'PASS: real Frida struct returns and allocator cleanup; ARM64-only matrix argument check skipped')
        finally:
            if session is not None:
                session.detach()
            device.kill(pid)


if __name__ == '__main__':
    main()
