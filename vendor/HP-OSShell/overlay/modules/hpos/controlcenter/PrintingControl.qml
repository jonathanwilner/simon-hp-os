pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.modules.common.widgets
import qs.modules.iris.components
import qs.modules.iris.style
import qs.modules.hpos.design

// Native control-center entry. Shared fleet package owns discovery and print jobs.
ColumnLayout {
    id: root
    property bool expanded: false
    signal detailsRequested()
    readonly property var panel: details.item
    readonly property string stateText: details.status === Loader.Error
        ? HposTokens.tr("Printing component unavailable", "打印组件不可用")
        : panel?.busy ? HposTokens.tr("Working…", "正在处理…")
        : panel?.ready ? HposTokens.tr("Find nearby printers", "查找附近打印机")
        : HposTokens.tr("Set up printing radio", "设置打印无线适配器")
    function refresh() { if (panel && !panel.busy) panel.start(["doctor"]); }
    spacing: 8 * IrisStyle.density
    IrisButton {
        id: card
        Layout.fillWidth: true
        implicitHeight: 66 * IrisStyle.density
        buttonRadius: 16 * IrisStyle.density
        colBackground: IrisStyle.fillQuiet
        colBackgroundHover: IrisStyle.fillHover
        activeFocusOnTab: true
        Accessible.name: "Nearby printing: " + root.stateText
        onClicked: root.detailsRequested()
        RowLayout {
            anchors.fill: parent
            anchors.margins: 10 * IrisStyle.density
            spacing: 10 * IrisStyle.density
            IrisIconButton {
                implicitWidth: 42 * IrisStyle.density
                implicitHeight: 42 * IrisStyle.density
                buttonRadius: height / 2
                materialIcon: "print"
                colBackground: root.expanded ? IrisStyle.accent : IrisStyle.fill
                colBackgroundHover: root.expanded ? IrisStyle.accent : IrisStyle.fillHover
                foreground: root.expanded ? IrisStyle.inkOnAccent : IrisStyle.text
                Accessible.name: HposTokens.tr("Open nearby printing", "打开附近打印")
                onClicked: root.detailsRequested()
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2 * IrisStyle.density
                IrisText { text: HposTokens.tr("Nearby printing", "附近打印"); font.pixelSize: IrisStyle.typeLabel; color: IrisStyle.text }
                IrisText { Layout.fillWidth: true; text: root.stateText; font.pixelSize: IrisStyle.typeCaption; color: IrisStyle.subtext; elide: Text.ElideRight }
            }
            MaterialSymbol { text: root.expanded ? "expand_less" : "chevron_right"; iconSize: 22 * IrisStyle.density; color: IrisStyle.subtext }
        }
    }
    Loader {
        id: details
        Layout.fillWidth: true
        Layout.preferredHeight: visible ? 480 * IrisStyle.density : 0
        visible: root.expanded
        // Keep the print job alive while details close.
        source: "file://" + (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/hp-os/printing/PrintingPanel.qml"
        onLoaded: item.compact = true
    }
    Binding { target: details.item; property: "errorColor"; value: IrisStyle.danger; when: !!details.item }
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
        text: HposTokens.tr("Install the fleet printing component to discover nearby printers.", "请安装设备群打印组件以查找附近打印机。")
        wrapMode: Text.WordWrap
        color: IrisStyle.subtext
    }
}
