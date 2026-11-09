import QtQuick

Rectangle {
    id: root
    width: 1280; height: 800; color: "#101820"
    property int selectedSession: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property bool busy: false
    property string message: "Sign in to your workspace"
    property string pendingPower: ""
    function login() {
        if (busy || !username.text.trim()) return;
        busy = true; message = "Signing in…";
        sddm.login(username.text.trim(), password.text, selectedSession);
    }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false; root.message = "Sign-in failed. Check your password and try again.";
            password.text = ""; password.forceActiveFocus();
        }
    }
    component Action: Rectangle {
        property string label
        signal clicked()
        width: 300; height: 44; radius: 8
        color: enabled ? (mouse.containsMouse ? "#23556a" : "#173d50") : "#27323a"
        border.color: activeFocus ? "#6bdcff" : "#346075"
        opacity: enabled ? 1 : 0.5
        activeFocusOnTab: true
        Text { anchors.centerIn: parent; text: parent.label; color: "white"; font.pixelSize: 15 }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: parent.clicked() }
        Keys.onReturnPressed: clicked()
        Keys.onSpacePressed: clicked()
    }
    Column {
        anchors.centerIn: parent; width: 420; spacing: 18
        Text { text: "HP-OS"; color: "#ffffff"; font.pixelSize: 58; font.weight: Font.Light }
        Text { text: sddm.hostName; color: "#9eb2c0"; font.pixelSize: 14; width: parent.width; elide: Text.ElideRight }
        Text { text: root.message; color: "#c8d9e3"; font.pixelSize: 15; width: parent.width; wrapMode: Text.Wrap }
        Rectangle {
            width: parent.width; height: 48; radius: 8; color: "#1b2b38"; border.color: username.activeFocus ? "#6bdcff" : "#405563"
            TextInput {
                id: username; anchors.fill: parent; anchors.margins: 14
                text: userModel.lastUser; color: "white"; font.pixelSize: 16; clip: true
                selectByMouse: true; enabled: !root.busy
                KeyNavigation.tab: password
                Keys.onReturnPressed: password.forceActiveFocus()
                Text { text: "Username"; color: "#9eb2c0"; visible: !username.text && !username.activeFocus }
            }
        }
        Rectangle {
            width: parent.width; height: 48; radius: 8; color: "#1b2b38"; border.color: password.activeFocus ? "#6bdcff" : "#405563"
            TextInput {
                id: password; anchors.fill: parent; anchors.margins: 14
                color: "white"; font.pixelSize: 16; clip: true; echoMode: TextInput.Password
                enabled: !root.busy; selectByMouse: true
                Keys.onReturnPressed: root.login()
                Text { text: "Password"; color: "#9eb2c0"; visible: !password.text && !password.activeFocus }
            }
        }
        Action { width: parent.width; label: root.busy ? "Signing in…" : "Sign in"; enabled: !root.busy; onClicked: root.login() }
        Text { text: "Desktop"; color: "#9eb2c0"; font.pixelSize: 13 }
        Flow {
            width: parent.width; spacing: 8
            Repeater {
                model: sessionModel
                delegate: Action {
                    required property int index
                    required property string name
                    required property string file
                    width: 202; height: 36
                    label: name; enabled: !root.busy
                    border.color: root.selectedSession === index ? "#6bdcff" : "#346075"
                    onClicked: { root.selectedSession = index; password.forceActiveFocus(); }
                    Component.onCompleted: {
                        if (file.split("/").pop() === config.preferredSession) root.selectedSession = index;
                    }
                }
            }
        }
        Row {
            spacing: 12
            Action { width: 204; label: "Restart"; enabled: sddm.canReboot && !root.busy; onClicked: root.pendingPower = "restart" }
            Action { width: 204; label: "Shut down"; enabled: sddm.canPowerOff && !root.busy; onClicked: root.pendingPower = "shutdown" }
        }
        Row {
            visible: root.pendingPower !== ""; spacing: 12
            Action { width: 204; label: "Confirm " + root.pendingPower; onClicked: { if (root.pendingPower === "restart") sddm.reboot(); else sddm.powerOff(); } }
            Action { width: 204; label: "Cancel"; onClicked: root.pendingPower = "" }
        }
    }
    Component.onCompleted: { if (username.text) password.forceActiveFocus(); else username.forceActiveFocus(); }
}
