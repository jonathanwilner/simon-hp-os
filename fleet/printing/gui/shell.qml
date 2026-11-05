//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma UseQApplication
//@ pragma ShellId hp-os-aware-print
import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
    FloatingWindow {
        id: window
        title: "HP-OS · Nearby printing"
        implicitWidth: 520; implicitHeight: 760
        minimumSize: Qt.size(440, 560)
        visible: true
        color: panel.palette.window
        PrintingPanel { id: panel; anchors.fill: parent }
        onClosed: Qt.quit()
    }
    IpcHandler {
        target: "printing"
        function open(): void { window.visible = true; }
    }
}
