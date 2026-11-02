#!/usr/bin/env python3
"""Remove DMS's periodic Wi-Fi scans; keep discovery on demand."""
from pathlib import Path
import sys


def replace_once(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise ValueError(f"Unsupported DMS scan anchor in {path}")
    path.write_text(text.replace(old, new, 1))


def patch(shell):
    service = shell / "Services/DMSNetworkService.qml"
    text = service.read_text()
    marker = "    // FLEET_DMS_WIFI_ON_DEMAND: NetworkManager owns background discovery.\n"
    if marker not in text:
        timer = '''    Timer {
        interval: 10000
        repeat: true
        running: root.autoScan && root.networkAvailable && root.wifiEnabled
        onTriggered: root.scanWifi()
    }
'''
        connected_timer = timer.replace("root.wifiEnabled\n", "root.wifiEnabled && !root.wifiConnected\n")
        if timer in text:
            replace_once(service, timer, marker)
        elif connected_timer in text:
            replace_once(service, connected_timer, marker)
        elif "onTriggered: root.scanWifi()" not in text:
            # DMS 1.5 has no QML scan timer. Preserve that revision unchanged.
            print("DMS has no periodic QML Wi-Fi scan timer; no change needed")
            return
        else:
            raise ValueError("Unsupported DMS Wi-Fi scan timer revision")
    for name, root in (
        ("Modules/ControlCenter/Details/NetworkDetail.qml", "root"),
        ("Modules/Settings/NetworkWifiTab.qml", "networkWifiTab"),
    ):
        replace_once(
            shell / name,
            f"    id: {root}\n",
            f"    id: {root}\n"
            "    // Discover once when the Wi-Fi list is opened, even if cached.\n"
            "    onVisibleChanged: {\n"
            "        if (visible && NetworkService.wifiEnabled)\n"
            "            NetworkService.scanWifi();\n"
            "    }\n",
        )


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
