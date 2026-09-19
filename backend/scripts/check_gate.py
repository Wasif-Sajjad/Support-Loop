"""Epic H3 — thin CI wrapper. run_eval.py already exits non-zero on failure, so this
script mainly exists as a documented, separate CI step per docs/architecture.md Part 6.
"""
import subprocess
import sys

result = subprocess.run([sys.executable, "scripts/run_eval.py"])
sys.exit(result.returncode)
