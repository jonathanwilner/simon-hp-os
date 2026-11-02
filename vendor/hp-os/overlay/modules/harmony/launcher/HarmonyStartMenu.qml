import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import qs.modules.harmony.design
import qs.modules.harmony.components

PanelWindow {
    id: root
    signal settingsRequested()
    visible: HarmonyStartState.opened
    screen: GlobalStates.focusedScreen ?? Quickshell.screens[0]
    anchors { top: true; left: true; right: true; bottom: true }
    margins.bottom: Math.max(28, Math.min(64, Number(Config.options?.iris?.dock?.iconSize ?? 48))) + 32
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "hp-start-dismiss"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    property string submenu: ""
    property bool confirmLogout: false
    function close() { HarmonyStartState.opened = false }
    Connections {
        target: HarmonyStartState
        function onAccountDetailsRequested() { if (HarmonyStartState.opened) account.open() }
        function onOpenedChanged() {
            if (HarmonyStartState.opened) panel.forceActiveFocus()
            else { root.submenu = ""; root.confirmLogout = false; account.close() }
        }
    }
    MouseArea { anchors.fill: parent; onClicked: root.close() }
    PanelWindow {
        id: surface
        visible: HarmonyStartState.opened
        screen: root.screen
        anchors { left: true; bottom: true }
        margins.left: 8
        margins.bottom: root.margins.bottom + 8
        implicitWidth: Math.min(680, (screen?.width ?? 1280) - 16)
        implicitHeight: Math.min(752, (screen?.height ?? 800) - root.margins.bottom - 16)
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "harmony-start-menu"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: 20
        color: HarmonyTokens.dark ? "#b0242730" : "#b0f5f7fa"
        border.color: HarmonyTokens.outline
        MouseArea { anchors.fill: parent; onClicked: root.submenu = "" }
        focus: true
        Keys.onEscapePressed: {
            if (root.confirmLogout) root.confirmLogout = false
            else if (root.submenu) root.submenu = ""
            else root.close()
        }
        Component.onCompleted: forceActiveFocus()
        HarmonyText { x: 36; y: 28; text: HarmonyTokens.tr("Recent files", "最近文件") }
        Item {
            x: 28; y: 70; width: parent.width - 56; height: Math.max(80, appArea.y - y - 20)
            Column {
                anchors.horizontalCenter: parent.horizontalCenter; y: Math.min(40, parent.height * 0.1); spacing: 12
                visible: HarmonyStartState.files.length === 0
                MaterialSymbol { anchors.horizontalCenter: parent.horizontalCenter; text: "folder_open"; iconSize: 84; color: HarmonyTokens.secondary; opacity: 0.35 }
                HarmonyText { anchors.horizontalCenter: parent.horizontalCenter; text: HarmonyTokens.tr("No files", "暂无文件"); color: HarmonyTokens.secondary }
                HarmonyText { anchors.horizontalCenter: parent.horizontalCenter; width: Math.min(440, panel.width - 80); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: HarmonyTokens.tr("Recently opened files will be shown here.", "最近打开的文件将显示在这里。"); color: HarmonyTokens.secondary }
            }
            ListView {
                anchors.fill: parent; clip: true; spacing: 4
                model: HarmonyStartState.files
                delegate: ItemDelegate {
                    required property var modelData
                    width: ListView.view.width; height: 58
                    onClicked: HarmonyStartState.openFile(modelData.url)
                    background: Rectangle { radius: 8; color: parent.hovered ? "#190a59f7" : "transparent" }
                    contentItem: RowLayout {
                        spacing: 12
                        MaterialSymbol { text: "description"; iconSize: 28; color: HarmonyTokens.accent }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 2
                            HarmonyText { Layout.fillWidth: true; text: modelData.name; elide: Text.ElideRight }
                            HarmonyText { Layout.fillWidth: true; text: modelData.path; font.pixelSize: 12; color: HarmonyTokens.secondary; elide: Text.ElideMiddle }
                        }
                    }
                    Accessible.name: modelData.name
                }
            }
        }
        Item {
            id: appArea
            x: 36; width: parent.width - 72; height: 148
            anchors.bottom: footer.top
            HarmonyText { y: 8; text: HarmonyTokens.tr("Recent apps", "最近应用") }
            Button {
                anchors.right: parent.right; y: 0; height: 36
                text: HarmonyTokens.tr("All ›", "全部 ›")
                font.family: HarmonyTokens.fontFamily
                onClicked: { HarmonyStartState.showAll() }
                background: Rectangle { radius: 8; color: parent.hovered ? "#190a59f7" : "transparent" }
                contentItem: HarmonyText { text: parent.text; color: HarmonyTokens.secondary; verticalAlignment: Text.AlignVCenter }
            }
            ListView {
                x: -12; y: 38; width: parent.width + 24; height: 106
                orientation: ListView.Horizontal; clip: true
                model: HarmonyStartState.apps
                delegate: ItemDelegate {
                    required property var modelData
                    width: 101; height: 104
                    onClicked: HarmonyStartState.openApp(modelData)
                    background: Rectangle { radius: 10; color: parent.hovered ? "#190a59f7" : "transparent" }
                    Image {
                        id: icon
                        anchors.horizontalCenter: parent.horizontalCenter; y: 8
                        width: 54; height: 54; sourceSize: Qt.size(108,108)
                        source: modelData.icon && (String(modelData.icon).includes("/") || Quickshell.hasThemeIcon(modelData.icon)) ? Quickshell.iconPath(modelData.icon, true) : ""
                        visible: status === Image.Ready
                    }
                    Image { anchors.fill: icon; visible: !icon.visible; source: Qt.resolvedUrl("../../../assets/harmony-application.svg") }
                    HarmonyText { x: 4; y: 68; width: parent.width - 8; text: modelData.name; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; font.pixelSize: 13 }
                    Accessible.name: modelData.name
                }
            }
        }
        Rectangle {
            id: footer
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 64; color: "transparent"; clip: true
            Rectangle {
                y: -panel.radius; width: parent.width; height: parent.height + panel.radius
                radius: panel.radius
                color: HarmonyTokens.dark ? "#20ffffff" : "#1affffff"
            }

            Button {
                id: userButton
                x: 28; anchors.verticalCenter: parent.verticalCenter; height: 48; width: Math.min(230, panel.width - 180)
                onClicked: root.submenu = root.submenu === "user" ? "" : "user"
                background: Rectangle { radius: 10; color: parent.hovered ? "#190a59f7" : "transparent" }
                contentItem: RowLayout {
                    spacing: 12
                    MaterialSymbol { text: "account_circle"; iconSize: 40; color: HarmonyTokens.secondary }
                    HarmonyText { text: SystemInfo.username; Layout.fillWidth: true; elide: Text.ElideRight }
                }
                Accessible.name: HarmonyTokens.tr("User account", "用户账户")
            }
            Button { anchors.right: power.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "settings"; width: 40; height: 40; Accessible.name: "Settings"; background: Rectangle { radius: 8; color: parent.hovered ? "#190a59f7" : "transparent" } contentItem: MaterialSymbol { text: parent.text; iconSize: 24; color: HarmonyTokens.text } onClicked: { root.settingsRequested(); root.close() } }
            Button { id: power; anchors.right: parent.right; anchors.rightMargin: 28; anchors.verticalCenter: parent.verticalCenter; text: "power_settings_new"; width: 40; height: 40; Accessible.name: "Power"; background: Rectangle { radius: 8; color: parent.hovered ? "#190a59f7" : "transparent" } contentItem: MaterialSymbol { text: parent.text; iconSize: 24; color: HarmonyTokens.text } onClicked: root.submenu = root.submenu === "power" ? "" : "power" }
        }
        Rectangle {
            visible: root.submenu.length > 0
            x: root.submenu === "power" ? parent.width - width - 24 : 24
            y: footer.y - height - 8; width: 240
            height: menuColumn.implicitHeight + 16
            radius: 12; color: HarmonyTokens.surface; border.color: HarmonyTokens.outline
            Column {
                id: menuColumn; x: 8; y: 8; width: parent.width - 16
                Button { visible: root.submenu === "user"; width: parent.width; text: HarmonyTokens.tr("Current user: ", "当前用户：") + SystemInfo.username; onClicked: { root.submenu = ""; account.open() } }
                Button { visible: root.submenu === "power"; width: parent.width; text: HarmonyTokens.tr("Lock screen", "锁屏"); onClicked: { HarmonyStartState.lock() } }
                Button { visible: root.submenu === "user"; width: parent.width; text: HarmonyTokens.tr("Log out", "退出登录"); onClicked: { root.submenu = ""; root.confirmLogout = true } }
                Button { visible: root.submenu === "user"; width: parent.width; text: HarmonyTokens.tr("User settings", "用户设置"); onClicked: { root.submenu = ""; HarmonyStartState.openAccountSettings() } }
            }
        }
        Dialog {
            id: account; anchors.centerIn: parent; modal: true
            title: HarmonyTokens.tr("Account details", "账户详情")
            standardButtons: Dialog.Close
            ColumnLayout {
                HarmonyText { text: SystemInfo.username }
                HarmonyText { text: Quickshell.env("HOME"); Layout.maximumWidth: panel.width - 100; elide: Text.ElideMiddle }
                Button { text: HarmonyTokens.tr("Open Home", "打开主目录"); onClicked: { account.close(); HarmonyStartState.openFile("file://" + Quickshell.env("HOME")) } }
                Button { text: "HP-OS Settings"; onClicked: { account.close(); root.settingsRequested(); root.close() } }
            }
        }
        Dialog {
            anchors.centerIn: parent; modal: true; visible: root.confirmLogout
            title: HarmonyTokens.tr("Log out?", "退出登录？")
            standardButtons: Dialog.Ok | Dialog.Cancel
            onAccepted: { HarmonyStartState.logOut() }
            onRejected: root.confirmLogout = false
            HarmonyText { text: HarmonyTokens.tr("Your open applications will close.", "打开的应用将关闭。"); wrapMode: Text.WordWrap }
        }
    }
}
}
