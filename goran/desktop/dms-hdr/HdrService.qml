pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Common
import qs.Services

Singleton {
    id: root
    property bool hdrEnabled: true
    property int whiteLevel: 500
    property bool available: false
    property bool busy: false
    property string errorText: ""
    signal settingsApplied(int white)

    function run(args, notify) {
        if (busy)
            return;
        busy = true;
        Proc.runCommand("niriHdr.control", ["goran-hdr"].concat(args), (stdout, exitCode) => {
            busy = false;
            if (exitCode !== 0) {
                errorText = "HDR settings could not be applied. The previous settings are retained.";
                if (notify)
                    ToastService.showError("Niri HDR", errorText);
                return;
            }
            try {
                const state = JSON.parse(stdout);
                hdrEnabled = state.enabled;
                whiteLevel = state.reference_luminance;
                available = true;
                errorText = "";
                if (notify)
                    settingsApplied(whiteLevel);
            } catch (error) {
                available = false;
                errorText = "Could not read HDR settings.";
            }
        }, 50, 20000);
    }
    function refresh() { run(["status"], false); }
    function apply(enabled, white) { run(["set", enabled ? "on" : "off", String(white)], true); }
    function reset() { run(["reset"], true); }
    Component.onCompleted: refresh()
    Timer { interval: 30000; running: true; repeat: true; onTriggered: root.refresh() }

    // IPC uses the same methods as the visible controls, for automation and verification.
    IpcHandler {
        target: "niri-hdr"
        function status(): string {
            return JSON.stringify({enabled: root.hdrEnabled, reference_luminance: root.whiteLevel,
                available: root.available, busy: root.busy, error: root.errorText});
        }
        function setHdr(enabled: bool): string { root.apply(enabled, root.whiteLevel); return "REQUESTED"; }
        function setWhite(nits: int): string { root.apply(root.hdrEnabled, nits); return "REQUESTED"; }
        function reset(): string { root.reset(); return "REQUESTED"; }
        function refresh(): string { root.refresh(); return "REQUESTED"; }
    }
}
