with open('/usr/local/bin/pyarmor_python', 'w') as f:
    f.write('''#!/usr/bin/env python3
import sys
import os
from pyarmor.pytransform import pyarmor_runtime
pyarmor_runtime()
import runpy
if len(sys.argv) < 2:
    print("Usage: pyarmor_python <script_to_run> [args...]")
    sys.exit(1)
script_to_run = sys.argv[1]
script_dir = os.path.dirname(os.path.abspath(script_to_run))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
sys.argv = sys.argv[1:]
runpy.run_path(script_to_run, run_name="__main__")
''')
import os
os.chmod('/usr/local/bin/pyarmor_python', 0o755)
