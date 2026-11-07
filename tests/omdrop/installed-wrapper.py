"""Exercise the installed wrapper with a hostile inherited SHELL and probe core.

Only the immutable core executable path is replaced. The installed wrapper's
shell syntax, argument forwarding, and environment setup execute unchanged.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

package = Path(sys.argv[1])
wrapper = (package / "bin/omdrop").read_text()
core = str(package / "lib/omdrop-core/omdrop")
assert wrapper.count('"' + core + '"') == 1, "Cannot locate installed core invocation"
with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    probe = directory / "probe"
    probe.write_text("#!" + sys.executable + "\nimport os, sys\nassert 'SHELL' not in os.environ\nassert os.environ['OMDROP_IMPLEMENTATION'] == 'rust'\nassert sys.argv[1:] == ['status', '--json']\n")
    probe.chmod(0o755)
    test_wrapper = directory / "omdrop"
    test_wrapper.write_text(wrapper.replace('"' + core + '"', '"' + str(probe) + '"'))
    test_wrapper.chmod(0o755)
    env = dict(os.environ, SHELL="/nix/store/not-in-etc-shells/bin/bash")
    subprocess.run([str(test_wrapper), "status", "--json"], env=env, check=True)
    for action in ["install-core", "install-driver"]:
        assert subprocess.run([str(test_wrapper), action], env=env, capture_output=True).returncode == 2
print("Installed Omdrop wrapper environment and argument contract passed")
