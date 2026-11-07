"""Assert rendered feature flags affect readiness for a real switching request."""
import importlib.util
from importlib.machinery import SourceFileLoader
import sys
import tempfile
from unittest.mock import patch

path, expected = sys.argv[1:]
spec = importlib.util.spec_from_loader("controller", SourceFileLoader("controller", path))
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
expected = expected == "true"
assert controller.ALLOW_STEERING is expected
wifi = dict(interface="wlan0", original_uuid="saved", original_bssid="aa",
            current={"channel": 153}, target={"bssid": "bb", "channel": 44})
with tempfile.TemporaryDirectory() as runtime, patch.dict(controller.os.environ, XDG_RUNTIME_DIR=runtime), patch.object(controller, "snapshot", return_value=wifi):
    report = controller.report()
assert report["can_enable"] is expected, report
assert report["reason"] == ("compatible_ap" if expected else "steering_disabled"), report
print("Rendered controller default/opt-out behavior passed:", expected)
