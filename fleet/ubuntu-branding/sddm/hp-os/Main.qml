import QtQuick

Rectangle {
    id: root
    width: 1280; height: 800; color: "#030914"
    property bool reducedMotion: String(config.reducedMotion).toLowerCase() === "true"
    property bool entranceDone: false
    property bool raised: reducedMotion
    property bool promptVisible: reducedMotion
    onPromptVisibleChanged: { if (promptVisible) { if(username.text) password.forceActiveFocus(); else username.forceActiveFocus(); } }
    property bool choosingSession: false
    property bool changingUser: !userModel.lastUser
    property string selectedName: "Desktop"
    property real uiScale: Math.min(2, Math.max(0.85, height / 900))
    property bool entered: reducedMotion
    property bool authenticated: false
    property real flight: 0
    property string brandFont: forma.status === FontLoader.Ready ? forma.name : "HP Forma DJR Office"
    FontLoader { id: forma; source: "fonts/HPForma-Regular.ttf" }
    Image { anchors.fill: parent; source: "images/starfield.png"; fillMode: Image.PreserveAspectCrop; opacity: 0.5; asynchronous: true }
    StarFlight { width: parent.width / 2; height: parent.height / 2; scale: 2; transformOrigin: Item.TopLeft; phase: root.flight; warp: root.busy ? 1.0 : 0.12; opacity: 0.75 }
    Timer { interval: 50; running: !root.reducedMotion && (!root.entranceDone || root.busy) && !root.authenticated; repeat: true; onTriggered: root.flight += root.busy ? 0.045 : 0.008 }
    Rectangle { anchors.fill: parent; color: "#030914"; opacity: root.entered ? 0 : 1; Behavior on opacity { NumberAnimation { duration: root.reducedMotion ? 0 : 1200 } } }
    Timer { interval: 250; running: !root.reducedMotion; onTriggered: root.entered = true }
    Timer { interval: 4000; running: true; onTriggered: root.entranceDone = true }
    Timer { interval: 1600; running: !root.reducedMotion; onTriggered: root.raised = true }
    Timer { interval: 2650; running: !root.reducedMotion; onTriggered: root.promptVisible = true }
    Text {
        font.family: root.brandFont; text: "HP-OS"; color: "white"
        font.pixelSize: 112 * root.uiScale; font.letterSpacing: -5 * root.uiScale
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * (root.raised ? 0.24 : 0.5) - height / 2
        scale: root.raised ? 0.57 : 1
        opacity: root.entered ? 1 : 0
        Behavior on y { NumberAnimation { duration: root.reducedMotion ? 0 : 1100; easing.type: Easing.InOutCubic } }
        Behavior on scale { NumberAnimation { duration: root.reducedMotion ? 0 : 1100; easing.type: Easing.InOutCubic } }
        Behavior on opacity { NumberAnimation { duration: root.reducedMotion ? 0 : 650 } }
    }
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
        function onLoginSucceeded() { root.authenticated = true; root.message = "Welcome to HP-OS"; }
        function onLoginFailed() {
            root.busy = false; root.entranceDone = true; root.promptVisible = true; root.raised = true; root.message = "Sign-in failed. Check your password and try again.";
            password.text = ""; password.forceActiveFocus();
        }
    }
    component Action: Rectangle {
        property string label
        property bool primary: false
        signal clicked()
        width: 300; height: 44; radius: 8
        color: primary ? (mouse.containsMouse ? "#125ee9" : "#024ad8") : enabled ? (mouse.containsMouse ? "#23556a" : "#173d50") : "#27323a"
        border.color: activeFocus ? "#6bdcff" : "#346075"
        opacity: enabled ? 1 : 0.5
        activeFocusOnTab: true
        Text { font.family: root.brandFont; anchors.centerIn: parent; width: parent.width - 20; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: parent.label; color: "white"; font.pixelSize: 15 }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: parent.clicked() }
        Keys.onReturnPressed: clicked()
        Keys.onSpacePressed: clicked()
    }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.37 + (root.promptVisible ? 0 : 28 * root.uiScale)
        width: 360; spacing: 12
        transformOrigin: Item.Top
        scale: root.uiScale
        opacity: root.authenticated ? 0 : (root.promptVisible ? 1 : 0)
        visible: opacity > 0
        Behavior on y { NumberAnimation { duration: root.reducedMotion ? 0 : 650; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: root.reducedMotion ? 0 : 650 } }
        Rectangle { width: 32; height: 2; color: "#024ad8"; anchors.horizontalCenter: parent.horizontalCenter }
        Text { font.family: root.brandFont; text: "Welcome back"; color: "white"; font.pixelSize: 24; anchors.horizontalCenter: parent.horizontalCenter }
        Text { font.family: root.brandFont; text: username.text || "Choose your account"; color: "#91a6bb"; font.pixelSize: 14; anchors.horizontalCenter: parent.horizontalCenter }
        Text { font.family: root.brandFont; text: root.message; color: "#c8d9e3"; font.pixelSize: 13; width: parent.width; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; visible: root.message !== "Sign in to your workspace" }
        Rectangle {
            visible: root.changingUser
            width: parent.width; height: 48; radius: 8; color: "#1b2b38"; border.color: username.activeFocus ? "#6bdcff" : "#405563"
            TextInput { font.family: root.brandFont;
                id: username; anchors.fill: parent; anchors.margins: 14
                text: userModel.lastUser; color: "white"; font.pixelSize: 16; clip: true
                selectByMouse: true; enabled: !root.busy
                KeyNavigation.tab: password
                Keys.onReturnPressed: password.forceActiveFocus()
                Text { font.family: root.brandFont; text: "Username"; color: "#9eb2c0"; visible: !username.text && !username.activeFocus }
            }
        }
        Rectangle {
            width: parent.width; height: 48; radius: 8; color: "#1b2b38"; border.color: password.activeFocus ? "#6bdcff" : "#405563"
            TextInput { font.family: root.brandFont;
                id: password; anchors.fill: parent; anchors.margins: 14
                color: "white"; font.pixelSize: 16; clip: true; echoMode: TextInput.Password
                enabled: !root.busy; selectByMouse: true
                Keys.onReturnPressed: root.login()
                Text { font.family: root.brandFont; text: "Password"; color: "#9eb2c0"; visible: !password.text && !password.activeFocus }
            }
        }
        Action { primary: true; width: parent.width; label: root.busy ? "Signing in…" : "Sign in"; enabled: !root.busy; onClicked: root.login() }
        Action { width: parent.width; height: 32; color: "transparent"; border.width: 0; label: root.selectedName + " · Change"; onClicked: root.choosingSession = !root.choosingSession }
        Action { width: parent.width; height: 28; color: "transparent"; border.width: 0; label: root.changingUser ? "Use selected account" : "Switch user"; enabled: !root.changingUser || username.text.trim().length > 0; onClicked: { root.changingUser = !root.changingUser; if(root.changingUser) username.forceActiveFocus(); else password.forceActiveFocus(); } }
        Flow {
            visible: root.choosingSession
            width: parent.width; spacing: 8
            Repeater {
                model: sessionModel
                delegate: Action {
                    required property int index
                    required property string name
                    required property string file
                    width: 174; height: 32
                    label: name; enabled: !root.busy
                    border.color: root.selectedSession === index ? "#6bdcff" : "#346075"
                    onClicked: { root.selectedSession = index; root.selectedName = name; root.choosingSession = false; password.forceActiveFocus(); }
                    Component.onCompleted: {
                        if (file.split("/").pop() === config.preferredSession) { root.selectedSession = index; root.selectedName = name; }
                    }
                }
            }
        }
    }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 22 * root.uiScale
        scale: root.uiScale; transformOrigin: Item.Bottom; spacing: 8
        visible: root.promptVisible
        Row {
            spacing: 12
            Action { width: 144; height: 32; label: "Restart"; enabled: sddm.canReboot && !root.busy; onClicked: root.pendingPower = "restart" }
            Action { width: 144; height: 32; label: "Shut down"; enabled: sddm.canPowerOff && !root.busy; onClicked: root.pendingPower = "shutdown" }
        }
        Row {
            visible: root.pendingPower !== ""; spacing: 12
            Action { width: 144; height: 32; label: "Confirm " + root.pendingPower; onClicked: { if (root.pendingPower === "restart") sddm.reboot(); else sddm.powerOff(); } }
            Action { width: 144; height: 32; label: "Cancel"; onClicked: root.pendingPower = "" }
        }
    }
    Component.onCompleted: { if (username.text) password.forceActiveFocus(); else username.forceActiveFocus(); }
}
