pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs.modules.common.widgets
import qs.modules.iris.components
import qs.modules.iris.style
import qs.modules.hpos.design

ColumnLayout {
    id: root
    property bool expanded: false
    signal detailsRequested()
    property var state: ({})
    property string errorText: ""
    readonly property string detail: !state.configured ? HposTokens.tr("Connect this device", "连接此设备")
        : state.paused ? HposTokens.tr("Paused", "已暂停")
        : state.healthy ? HposTokens.tr("Clipboard sync on", "剪贴板同步已开启")
        : state.active ? HposTokens.tr("Checking connection…", "正在检查连接…") : HposTokens.tr("Sync stopped", "同步已停止")
    function refresh() { if (!status.running) status.running = true; }
    function toggle() {
        if (!state.configured) { launch.command = ["relay"]; launch.running = true; return; }
        action.command = ["relay-control", state.active && !state.paused ? "pause" : "resume"];
        action.running = true;
    }
    Component.onCompleted: refresh()
    Timer { interval: 5000; repeat: true; running: root.visible; onTriggered: root.refresh() }
    Process {
        id: status
        command: ["relay-control", "status"]
        stdout: StdioCollector { onStreamFinished: { try { root.state = JSON.parse(text); } catch(e) { root.errorText = "Relay status unavailable"; } } }
    }
    Process { id: launch }
    Process {
        id: action
        stderr: StdioCollector { onStreamFinished: if (text.trim()) root.errorText = text.trim() }
        onExited: root.refresh()
    }
    spacing: 8 * IrisStyle.density
    IrisButton {
        Layout.fillWidth: true
        implicitHeight: 66 * IrisStyle.density
        buttonRadius: 16 * IrisStyle.density
        colBackground: IrisStyle.fillQuiet
        colBackgroundHover: IrisStyle.fillHover
        Accessible.name: "Relay: " + root.detail
        onClicked: root.detailsRequested()
        RowLayout {
            anchors.fill: parent
            anchors.margins: 10 * IrisStyle.density
            spacing: 10 * IrisStyle.density
            IrisIconButton {
                implicitWidth: 42 * IrisStyle.density
                implicitHeight: 42 * IrisStyle.density
                buttonRadius: height / 2
                materialIcon: "content_paste"
                colBackground: root.state.healthy && !root.state.paused ? IrisStyle.accent : IrisStyle.fill
                foreground: root.state.healthy && !root.state.paused ? IrisStyle.inkOnAccent : IrisStyle.text
                enabled: !action.running && !launch.running
                Accessible.name: HposTokens.tr("Toggle Relay clipboard sync", "切换 Relay 剪贴板同步")
                Accessible.checkable: true
                Accessible.checked: root.state.active && !root.state.paused
                onClicked: root.toggle()
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2 * IrisStyle.density
                IrisText { text: "Relay"; font.pixelSize: IrisStyle.typeLabel }
                IrisText { Layout.fillWidth: true; text: root.detail; color: IrisStyle.subtext; font.pixelSize: IrisStyle.typeCaption; elide: Text.ElideRight }
            }
            MaterialSymbol { text: root.expanded ? "expand_less" : "chevron_right"; iconSize: 22 * IrisStyle.density; color: IrisStyle.subtext }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: root.expanded
        IrisText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: HposTokens.tr("Sync copied text between your connected devices. Open Relay to connect devices or view clipboard history.", "在已连接设备之间同步复制的文本。打开 Relay 可连接设备或查看剪贴板历史。") }
        IrisText { Layout.fillWidth: true; visible: !!root.errorText; text: root.errorText; wrapMode: Text.WordWrap; color: IrisStyle.danger }
        IrisButton {
            Layout.fillWidth: true
            text: root.state.configured ? HposTokens.tr("Open clipboard history", "打开剪贴板历史") : HposTokens.tr("Set up Relay", "设置 Relay")
            enabled: !launch.running
            onClicked: { launch.command = root.state.configured ? ["relay", "--history"] : ["relay"]; launch.running = true; }
        }
    }
}
