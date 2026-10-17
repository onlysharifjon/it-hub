"""Bounded child process: empty environment and no filesystem/network APIs in JS."""
import json
from pathlib import Path
import subprocess
import sys

WORKER = str(Path(__file__).with_name('js_worker.py'))

def execute(code, task=''):
    try:
        result = subprocess.run([sys.executable, '-I', WORKER], input=json.dumps({'code': code, 'task': task}),
            text=True, capture_output=True, timeout=2, env={}, cwd='/tmp', close_fds=True)
        if result.returncode or len(result.stdout) > 40000:
            raise ValueError('runner')
        return json.loads(result.stdout)
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return {'output': [], 'semantic': False, 'error': 'Kod tekshiruvi vaqtincha mavjud emas yoki limit tugadi.'}
