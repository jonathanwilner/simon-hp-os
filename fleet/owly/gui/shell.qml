//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma UseQApplication
//@ pragma ShellId hp-os-omdrop
import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
    FloatingWindow {
        id: window
        title: "Omdrop · AirDrop"
        implicitWidth: 520; implicitHeight: 760
        minimumSize: Qt.size(440, 560)
        visible: true
        color: panel.palette.window
        OmdropPanel { id: panel; anchors.fill: parent }
        onClosed: Qt.quit()
    }
    IpcHandler {
        target: "omdrop"
        function open(): void { window.visible = true; }
    }
}
