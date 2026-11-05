#!/usr/bin/env python3
"""Bounded AirDrop window with temporary, same-network AP steering.

Only the active saved connection is cloned. No credentials are read, no saved
profile is modified, and no exclusive radio mode is enabled. Independent user
systemd timers restore connectivity if this process or its GUI disappears.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

OMDROP = "@omdrop@/bin/omdrop"
OWLY = "@owly@/bin/owly"
SELF = "@out@/bin/hp-os-omdrop-controller"
CHANNELS = {6, 44, 149}
ALLOW_STEERING = "@allowSteering@" == "true"
UNITS = "hp-os-omdrop"
DEADLINE = None
os.environ["LC_ALL"] = "C"


class Failure(Exception):
    pass


def run(args, timeout=8, check=True):
    if DEADLINE is not None:
        timeout = min(timeout, DEADLINE - time.monotonic())
        if timeout <= 0:
            raise Failure("AirDrop startup deadline expired.")
    try:
        environment = os.environ.copy()
        if Path(args[0]).name in ("systemctl", "systemd-run"):
            environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + str(Path(os.environ["XDG_RUNTIME_DIR"]) / "bus")
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, env=environment)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Failure(f"{Path(args[0]).name} did not complete: {exc}") from exc
    if check and result.returncode:
        raise Failure(result.stderr.strip() or result.stdout.strip() or
                      f"{Path(args[0]).name} exited {result.returncode}")
    return result


def native(name):
    # Ubuntu's NM client must match Ubuntu's daemon. NixOS owns its system path.
    for directory in ("/usr/bin", "/run/current-system/sw/bin", "/usr/sbin"):
        path = Path(directory) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise Failure(f"The native {name} command is unavailable.")


def nm(*args, timeout=8, check=True):
    return run([native("nmcli"), "--wait", "15", *args], timeout, check)


def fields(line):
    """Split nmcli's escaped terse fields without misreading MAC colons."""
    result, field, escaped = [], [], False
    for char in line:
        if escaped:
            field.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            result.append("".join(field)); field = []
        else:
            field.append(char)
    result.append("".join(field))
    return result


def runtime():
    directory = os.environ.get("XDG_RUNTIME_DIR")
    if not directory:
        raise Failure("A logged-in desktop session is required.")
    path = Path(directory) / "hp-os-omdrop"
    path.mkdir(mode=0o700, exist_ok=True)
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise Failure("The AirDrop runtime directory has unsafe permissions.")
    return path


def read_state():
    try:
        return json.loads((runtime() / "controller.json").read_text())
    except FileNotFoundError:
        return None


def write_state(state):
    path = runtime() / "controller.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.chmod(0o600)
    temporary.replace(path)


@contextlib.contextmanager
def locked():
    with (runtime() / "controller.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def snapshot():
    radio = json.loads(run([OWLY, "doctor", "--json"], check=False).stdout)
    if radio.get("mode") != "shared" or not radio.get("hardware"):
        raise Failure("This adapter cannot safely share Wi-Fi with AirDrop. Exclusive radio mode is disabled.")
    active = []
    for line in nm("-t", "-f", "DEVICE,TYPE,STATE", "device", "status").stdout.splitlines():
        row = fields(line)
        if len(row) == 3 and row[1] == "wifi" and row[2] == "connected":
            active.append(row[0])
    if len(active) != 1:
        raise Failure("AirDrop steering requires exactly one connected Wi-Fi adapter.")
    interface = active[0]
    connections = [fields(line) for line in nm("-t", "-f", "DEVICE,UUID", "connection", "show", "--active").stdout.splitlines()]
    original_uuid = next((row[1] for row in connections if len(row) == 2 and row[0] == interface), None)
    if not original_uuid:
        raise Failure("The active saved Wi-Fi connection could not be identified.")
    rows = []
    for line in nm("-t", "-f", "IN-USE,SSID,BSSID,CHAN,SECURITY,SIGNAL", "device", "wifi", "list", "ifname", interface, "--rescan", "no").stdout.splitlines():
        row = fields(line)
        if len(row) == 6 and row[3].isdigit() and row[5].isdigit():
            rows.append(dict(active=row[0] == "*", ssid=row[1], bssid=row[2], channel=int(row[3]), security=row[4], signal=int(row[5])))
    current = next((row for row in rows if row["active"]), None)
    if not current:
        raise Failure("The current Wi-Fi access point is absent from NetworkManager's scan results.")
    candidates = [row for row in rows if row["ssid"] == current["ssid"]
                  and row["security"] == current["security"] and row["channel"] in CHANNELS]
    target = current if current["channel"] in CHANNELS else max(candidates, key=lambda row: row["signal"], default=None)
    return {"interface": interface, "original_uuid": original_uuid, "original_bssid": current["bssid"], "current": current, "target": target}


def report():
    state = read_state()
    if state:
        return {"can_enable": False, "reason": "managed_window", "message": state["message"], "phase": state["phase"], "managed": True}
    try:
        wifi = snapshot()
        target = wifi["target"]
        if not target:
            return {"can_enable": False, "reason": "no_compatible_ap", "message": "No access point on channels 6, 44 or 149 is available for this saved Wi-Fi network. Exclusive radio mode is disabled.", "phase": "idle"}
        steering = target["bssid"] != wifi["original_bssid"]
        if steering and not ALLOW_STEERING:
            return {"can_enable": False, "reason": "steering_disabled", "message": "Automatic Wi-Fi roaming is disabled. Connect this Wi-Fi network on channel 6, 44 or 149 before enabling AirDrop.", "phase": "idle", "needs_steering": True, "current_channel": wifi["current"]["channel"], "target_channel": target["channel"]}
        return {"can_enable": True, "reason": "compatible_ap" if steering else "compatible_channel", "message": f"AirDrop will temporarily use this Wi-Fi network's channel {target['channel']} access point and restore the original connection afterward." if steering else "The current Wi-Fi channel supports AirDrop.", "phase": "idle", "needs_steering": steering, "current_channel": wifi["current"]["channel"], "target_channel": target["channel"]}
    except Failure as exc:
        return {"can_enable": False, "reason": "wifi_unavailable", "message": str(exc), "phase": "idle"}


def systemctl(*args, check=True):
    return run([native("systemctl"), "--user", *args], timeout=6, check=check)


def stop_timer(suffix):
    systemctl("stop", f"{UNITS}-{suffix}.timer", check=False)
    systemctl("reset-failed", f"{UNITS}-{suffix}.service", check=False)


def arm_timer(suffix, seconds):
    stop_timer(suffix)
    # Restart retries a failed restoration even after the GUI has disappeared.
    run([native("systemd-run"), "--user", f"--unit={UNITS}-{suffix}",
         "--collect", f"--on-active={seconds}s", "--timer-property=AccuracySec=1s",
         "--property=Restart=on-failure", "--property=RestartSec=5s",
         "--property=StartLimitIntervalSec=0", SELF, "restore", read_state()["token"]], timeout=6)


def health_baseline(interface):
    # A known reachable tailnet peer proves remote management survived the roam.
    tailscale = native("tailscale")
    status = json.loads(run([tailscale, "status", "--json"]).stdout)
    peers = sorted(status.get("Peer", {}).values(), key=lambda peer: not peer.get("Active", False))
    peer_ip = None
    for peer in peers:
        if not peer.get("Online") or not peer.get("TailscaleIPs"):
            continue
        ip = peer["TailscaleIPs"][0]
        if run([tailscale, "ping", "--c", "1", "--timeout", "2s", ip], timeout=4, check=False).returncode == 0:
            peer_ip = ip
            break
        # Limit baseline probes; no radio change has happened at this point.
        if peers.index(peer) >= 2:
            break
    if not peer_ip:
        raise Failure("No existing Tailscale management peer is reachable. Wi-Fi was left unchanged.")
    health_check(interface, peer_ip)
    return peer_ip


def health_check(interface, peer_ip, retry=False):
    attempts = 3 if retry else 1
    for attempt in range(attempts):
        try:
            return health_once(interface, peer_ip)
        except Failure as exc:
            if attempt + 1 == attempts:
                raise Failure(f"Wi-Fi management connectivity did not recover: {exc}") from exc
            time.sleep(1)


def health_once(interface, peer_ip):
    routes = json.loads(run([native("ip"), "-j", "route", "show", "default", "dev", interface]).stdout)
    gateway = next((route.get("gateway") for route in routes if route.get("gateway")), None)
    if not gateway:
        raise Failure("The Wi-Fi default route is unavailable.")
    run([native("ping"), "-n", "-c", "1", "-W", "2", gateway], timeout=3)
    run([native("tailscale"), "ping", "--c", "1", "--timeout", "3s", peer_ip], timeout=5)


def restore_locked():
    global DEADLINE
    DEADLINE = None
    state = read_state()
    # A wedged backend must never prevent network restoration.
    try:
        run([OMDROP, "off"], timeout=10, check=False)
    except Failure:
        pass
    if not state:
        return
    state.update(phase="restoring", message="Restoring the original Wi-Fi connection.")
    write_state(state)
    if state.get("clone_uuid"):
        try:
            nm("connection", "up", "uuid", state["original_uuid"], "ifname", state["interface"], "ap", state["original_bssid"], timeout=20)
        except Failure:
            # Original AP may disappear. The original saved network is still
            # the only fallback, and its persistent preferences are unchanged.
            nm("connection", "up", "uuid", state["original_uuid"], "ifname", state["interface"], timeout=20)
        existing = nm("-g", "UUID", "connection", "show").stdout.splitlines()
        if state["clone_uuid"] in existing:
            nm("connection", "delete", "uuid", state["clone_uuid"])
    elif state.get("clone_name"):
        existing = nm("-g", "NAME", "connection", "show").stdout.splitlines()
        if state["clone_name"] in existing:
            nm("connection", "delete", "id", state["clone_name"])
    (runtime() / "controller.json").unlink(missing_ok=True)
    for suffix in ("rollback", "expiry"):
        stop_timer(suffix)


def duration(value):
    match = re.fullmatch(r"([1-9][0-9]*)(s|m)?", value)
    if not match:
        raise Failure("Use a bounded duration such as 10m.")
    seconds = int(match[1]) * (1 if match[2] == "s" else 60)
    if seconds > 1800:
        raise Failure("AirDrop windows are limited to 30 minutes.")
    return seconds


def enable(value):
    global DEADLINE
    seconds = duration(value)
    with locked():
        if read_state():
            raise Failure("An AirDrop window or Wi-Fi restoration is already in progress.")
        systemctl("stop", f"{UNITS}-monitor.service", check=False)
        wifi = snapshot()
        target = wifi["target"]
        if not target:
            raise Failure("No compatible access point exists on this saved Wi-Fi network. Wi-Fi was left unchanged.")
        steering = target["bssid"] != wifi["original_bssid"]
        if steering and not ALLOW_STEERING:
            raise Failure("Automatic Wi-Fi roaming is disabled. Connect on channel 6, 44 or 149 first.")
        peer_ip = health_baseline(wifi["interface"]) if steering else None
        state = {key: wifi[key] for key in ("interface", "original_uuid", "original_bssid")}
        state.update(token=str(uuid.uuid4()), phase="starting", message="Preparing the AirDrop receive window.", clone_uuid=None, expires=time.time() + seconds)
        state.update(notification_bus=os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
                     notification_display=os.environ.get("DISPLAY", ""),
                     notification_wayland_display=os.environ.get("WAYLAND_DISPLAY", ""))
        write_state(state)
        try:
            # This timer exists before any connection change. It survives
            # subprocess/GUI failure and the management connection dropping.
            arm_timer("rollback", 60)
            DEADLINE = time.monotonic() + 45
            if steering:
                name = "hp-os-omdrop-" + str(uuid.uuid4())
                state["clone_name"] = name
                write_state(state)
                nm("connection", "clone", "--temporary", "uuid", wifi["original_uuid"], name)
                clone_uuid = nm("-g", "connection.uuid", "connection", "show", name).stdout.strip()
                state.update(clone_uuid=clone_uuid, phase="steering", message=f"Temporarily switching this Wi-Fi network to channel {target['channel']} for AirDrop.")
                write_state(state)
                nm("connection", "modify", "--temporary", "uuid", clone_uuid,
                   "connection.autoconnect", "no", "802-11-wireless.bssid", target["bssid"],
                   "802-11-wireless.band", "bg" if target["channel"] == 6 else "a",
                   "802-11-wireless.channel", str(target["channel"]))
                nm("connection", "up", "uuid", clone_uuid, "ifname", wifi["interface"], "ap", target["bssid"], timeout=20)
                health_check(wifi["interface"], peer_ip, retry=True)
            state.update(phase="starting", message="Starting the AirDrop receive window.")
            write_state(state)
            run([OMDROP, "on", f"{seconds}s"], timeout=25)
            live = json.loads(run([OMDROP, "status", "--json"]).stdout)
            if not live.get("receiving"):
                raise Failure("AirDrop did not start receiving. Restoring the original connection.")
            arm_timer("expiry", seconds + 10)
            systemctl("reset-failed", f"{UNITS}-monitor.service", check=False)
            run([native("systemd-run"), "--user", f"--unit={UNITS}-monitor", "--collect", "--property=Restart=on-failure", "--property=RestartSec=5s", SELF, "monitor", state["token"]], timeout=6)
            state.update(expires=time.time() + seconds, phase="receiving", message="AirDrop is receiving. The original Wi-Fi connection will return when this window ends.")
            write_state(state)
            stop_timer("rollback")
            DEADLINE = None
        except BaseException:
            # The independent rollback unit will retry if restoration fails.
            try:
                restore_locked()
            except Failure as restore_error:
                state.update(phase="restore_failed", message=f"Wi-Fi restoration will retry: {restore_error}")
                write_state(state)
            raise


def monitor():
    # This service is independent of the GUI and its subprocess lifetime.
    while read_state():
        state = read_state()
        if not state or state["token"] != sys.argv[2]:
            return
        live = run([OMDROP, "status", "--json"], check=False)
        try:
            receiving = json.loads(live.stdout).get("receiving", False)
        except (ValueError, TypeError):
            receiving = False
        if not receiving or time.time() >= state["expires"]:
            with locked():
                if read_state() and read_state()["token"] == sys.argv[2]:
                    restore_locked()
            return
        time.sleep(3)


def main():
    os.umask(0o077)
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if command == "status":
            result = report()
        elif command == "on":
            enable(sys.argv[2] if len(sys.argv) > 2 else "10m")
            result = report()
        elif command in ("off", "restore"):
            with locked():
                if command == "restore" and (not read_state() or len(sys.argv) < 3 or read_state()["token"] != sys.argv[2]):
                    return 0
                if command == "off" and read_state():
                    arm_timer("rollback", 5)
                restore_locked()
            result = {"phase": "idle", "message": "AirDrop stopped; original Wi-Fi restored.", "can_enable": True, "reason": "stopped"}
        elif command == "monitor":
            monitor(); return 0
        else:
            raise Failure("Expected on, off or status --json.")
        print(json.dumps(dict(result, ok=True)))
        return 0
    except (Failure, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "can_enable": False, "reason": "operation_failed", "phase": "error", "message": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
