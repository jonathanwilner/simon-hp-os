pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.modules.common.widgets
import qs.modules.iris.components
import qs.modules.iris.style
import qs.modules.hpos.design

// Huawei Share interaction: the round icon controls receiving; the card opens details.
// Shared fleet package supplies the protocol controller and transfer UI.
ColumnLayout {
    id: root
    property bool expanded: false
    signal detailsRequested()
    readonly property var panel: details.item
    readonly property bool receiving: panel?.receiving ?? false
    readonly property string stateText: details.status === Loader.Error
        ? HposTokens.tr("Sharing component unavailable", "共享组件不可用")
        : !panel?.statusChecked ? HposTokens.tr("Checking…", "正在检查…")
        : panel.busy ? HposTokens.tr("Working…", "正在处理…")
        : panel.blocker ? HposTokens.tr("Wi-Fi needs attention", "请检查无线网络")
        : receiving ? HposTokens.tr("Receiving is on", "接收已开启")
        : HposTokens.tr("Off", "已关闭")
    function toggleReceiving() {
        if (!panel || panel.busy || !panel.statusChecked) return;
        if (receiving) panel.run(["off"]);
        else if (panel.checked && !panel.blocker) panel.run(["on", "10m"]);
        else detailsRequested();
    }
    function refresh() { if (panel) panel.refresh(); }
    spacing: 8 * IrisStyle.density
    IrisButton {
        id: card
        Layout.fillWidth: true
        implicitHeight: 66 * IrisStyle.density
        buttonRadius: 16 * IrisStyle.density
        colBackground: IrisStyle.fillQuiet
        colBackgroundHover: IrisStyle.fillHover
        activeFocusOnTab: true
        Accessible.name: "Omdrop · AirDrop: " + root.stateText
        onClicked: root.detailsRequested()
        RowLayout {
            anchors.fill: parent
            anchors.margins: 10 * IrisStyle.density
            spacing: 10 * IrisStyle.density
            IrisIconButton {
                implicitWidth: 42 * IrisStyle.density
                implicitHeight: 42 * IrisStyle.density
                buttonRadius: height / 2
                materialIcon: "nearby_share"
                colBackground: root.receiving ? IrisStyle.accent : IrisStyle.fill
                colBackgroundHover: root.receiving ? IrisStyle.accent : IrisStyle.fillHover
                foreground: root.receiving ? IrisStyle.inkOnAccent : IrisStyle.text
                enabled: !!root.panel && root.panel.statusChecked && !root.panel.busy
                Accessible.name: root.receiving ? HposTokens.tr("Stop receiving", "停止接收") : HposTokens.tr("Receive for 10 minutes", "接收十分钟")
                Accessible.checkable: true
                Accessible.checked: root.receiving
                onClicked: root.toggleReceiving()
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2 * IrisStyle.density
                IrisText { text: "Omdrop · AirDrop"; font.pixelSize: IrisStyle.typeLabel; color: IrisStyle.text }
                IrisText { Layout.fillWidth: true; text: root.stateText; font.pixelSize: IrisStyle.typeCaption; color: IrisStyle.subtext; elide: Text.ElideRight }
            }
            MaterialSymbol { text: root.expanded ? "expand_less" : "chevron_right"; iconSize: 22 * IrisStyle.density; color: IrisStyle.subtext }
        }
    }
    Loader {
        id: details
        Layout.fillWidth: true
        Layout.preferredHeight: visible ? 450 * IrisStyle.density : 0
        visible: root.expanded
        // Keep one controller alive when details close; polling is bounded by visibility/receiving.
        source: "file://" + (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/hp-os/omdrop/OmdropPanel.qml"
        onLoaded: item.compact = true
    }
    Binding { target: details.item; property: "palette.window"; value: IrisStyle.fill; when: !!details.item }
    Binding { target: details.item; property: "palette.base"; value: IrisStyle.fillQuiet; when: !!details.item }
    Binding { target: details.item; property: "palette.text"; value: IrisStyle.text; when: !!details.item }
    Binding { target: details.item; property: "palette.windowText"; value: IrisStyle.text; when: !!details.item }
    Binding { target: details.item; property: "palette.button"; value: IrisStyle.fillQuiet; when: !!details.item }
    Binding { target: details.item; property: "palette.buttonText"; value: IrisStyle.text; when: !!details.item }
    Binding { target: details.item; property: "palette.highlight"; value: IrisStyle.accent; when: !!details.item }
    Binding { target: details.item; property: "palette.highlightedText"; value: IrisStyle.inkOnAccent; when: !!details.item }
    IrisText {
        Layout.fillWidth: true
        visible: root.expanded && details.status === Loader.Error
        text: HposTokens.tr("Install the fleet Omdrop component to enable nearby sharing.", "请安装设备群 Omdrop 组件以启用附近共享。")
        wrapMode: Text.WordWrap
        color: IrisStyle.subtext
    }
}
