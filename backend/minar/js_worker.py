"""One-shot JS runtime. No host functions; kernel denies filesystem/network/process access."""
import ctypes
import json
import resource
import sys
import quickjs

payload = json.loads(sys.stdin.read(30000))
ctx = quickjs.Context()
ctx.set_memory_limit(16 * 1024 * 1024)
ctx.set_time_limit(0.4)
ctx.set_max_stack_size(256 * 1024)
resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
# Load before restricting syscalls. Fail closed if the kernel filter cannot be installed.
lib = ctypes.CDLL('libseccomp.so.2')
lib.seccomp_init.restype = ctypes.c_void_p
lib.seccomp_init.argtypes = [ctypes.c_uint32]
lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
lib.seccomp_load.argtypes = [ctypes.c_void_p]
f = lib.seccomp_init(0x7fff0000)
for name in ('open', 'openat', 'openat2', 'creat', 'socket', 'connect', 'socketpair', 'execve', 'execveat',
             'fork', 'vfork', 'clone', 'clone3', 'ptrace', 'process_vm_readv', 'process_vm_writev',
             'unlink', 'unlinkat', 'rename', 'renameat', 'mkdir', 'mount', 'io_uring_setup'):
    nr = lib.seccomp_syscall_resolve_name(name.encode())
    if nr >= 0 and lib.seccomp_rule_add(f, 0x00050001, nr, 0) != 0:
        raise RuntimeError('sandbox policy')
if lib.seccomp_load(f) != 0:
    raise RuntimeError('sandbox unavailable')
try:
    # Captured logs live in a closure, unavailable for writes by submitted code.
    ctx.eval('''globalThis.__getLogs = (() => {
      const logs = []; Object.setPrototypeOf(logs, null);
      const stringify = String, encode = JSON.stringify;
      const push = Function.prototype.call.bind(Array.prototype.push);
      const log = (...args) => { if (logs.length >= 100) throw Error('Log limiti');
        push(logs, args.map(x => stringify(x).slice(0,300)).join(' ').slice(0,300)); };
      Object.defineProperty(globalThis, 'console', {value:Object.freeze({log,info:log,warn:log,error:log}), writable:false});
      return () => encode(logs);
    })();''')
    get_logs = ctx.get('__getLogs')
    ctx.eval('delete globalThis.__getLogs')
    ctx.eval(payload['code'])
    semantic = True
    if payload.get('task') == 'js-5':
        semantic = bool(ctx.eval('typeof add === "function" && add(7,11) === 18 && add(-4,1) === -3 && add(0,0) === 0'))
    if payload.get('task') == 'js-8':
        semantic = bool(ctx.eval('hero.name === "Robo" && hero.level === 3'))
    print(json.dumps({'output': json.loads(get_logs()), 'semantic': semantic}))
except Exception:
    print(json.dumps({'output': [], 'error': 'Kod bajarilmadi yoki vaqt/xotira limiti tugadi.', 'semantic': False}))
