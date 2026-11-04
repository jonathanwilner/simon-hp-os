import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

// Native HP-OS/DMS presentation of Omdrop's JSON interface.
// Radar and interaction model derive from netmojo-systems/omdrop-plugin (MIT).
Pane {
    id: root
    property bool compact: false
    property string cli: "@omdrop@/bin/omdrop"
    property string radioCli: "@owly@/bin/owly"
    property var state: ({})
    property var radio: ({})
    property var peers: []
    property var identity: ({})
    readonly property bool contactsConfigured: ((identity.apple_files_on_disk || []).length === 3 || identity.onepassword_configured === true) && (state.senders || 0) > 0
    property bool checked: false
    property bool statusChecked: false
    property string errorText: ""
    property string progressText: ""
    readonly property bool receiving: state.receiving === true
    onReceivingChanged: { if (!receiving) peers = []; }
    readonly property string blocker: {
        if (!checked) return "Checking Wi-Fi radio…";
        if (radio.missing && radio.missing.length) return radio.missing.map(x => x.say).join("\n");
        return "";
    }
    readonly property bool busy: action.running || send.running
    padding: compact ? 12 : 18
    function refresh() {
        if (!status.running) status.running = true;
        if (!doctor.running) doctor.running = true;
        if (!identityPoll.running) identityPoll.running = true;
        if (receiving && !peerPoll.running) peerPoll.running = true;
    }
    function run(args) {
        if (busy) return;
        errorText = "";
        action.command = [cli].concat(args);
        action.running = true;
    }
    function sendTo(mac) {
        if (busy || blocker) return;
        progressText = "Choose files…";
        send.command = [cli, "send", "--pick", "--to", mac];
        send.running = true;
    }
    Component.onCompleted: refresh()
    Timer { interval: 4000; running: root.visible || root.receiving; repeat: true; onTriggered: root.refresh() }
    Process {
        id: doctor
        command: [root.radioCli, "doctor", "--json"]
        stdout: StdioCollector { onStreamFinished: {
            try { root.radio = JSON.parse(text); root.checked = true; }
            catch (e) { root.errorText = "The radio status could not be read."; }
        } }
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) root.errorText = text.trim(); } }
    }
    Process {
        id: status
        command: [root.cli, "status", "--json"]
        stdout: StdioCollector { onStreamFinished: {
            try { root.state = JSON.parse(text); root.statusChecked = true; }
            catch (e) { root.errorText = "Omdrop status could not be read."; }
        } }
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) root.errorText = text.trim(); } }
    }
    Process {
        id: identityPoll
        command: [root.cli, "identity", "status", "--json"]
        stdout: StdioCollector { onStreamFinished: {
            try { root.identity = JSON.parse(text); } catch (e) { root.identity = {}; }
        } }
    }
    Process {
        id: peerPoll
        command: [root.cli, "peers", "--json"]
        stdout: StdioCollector { onStreamFinished: {
            try { root.peers = root.receiving ? JSON.parse(text) : []; } catch (e) { root.peers = []; }
        } }
    }
    Process {
        id: action
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) root.errorText = text.trim(); } }
        onExited: (code, exitStatus) => {
            if (code !== 0 && !root.errorText) root.errorText = "Omdrop could not complete this action. Check the Wi-Fi status below.";
            root.refresh();
        }
    }
    Process {
        id: send
        stdout: SplitParser { onRead: data => { if (data.trim()) root.progressText = data.trim(); } }
        stderr: SplitParser { onRead: data => { if (data.trim()) root.progressText = data.trim(); } }
        onExited: (code, exitStatus) => {
            if (code === 0 && root.progressText === "Choose files…") root.progressText = "File selection closed.";
            else if (code !== 0) root.errorText = root.progressText === "Choose files…" ? "The file chooser or send operation could not complete." : root.progressText;
        }
    }
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 12
            Label { text: "Omdrop · AirDrop"; font.pixelSize: root.compact ? 20 : 24; font.bold: true }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: !root.checked ? "Checking radio…" : root.blocker ? "Wi-Fi needs attention" : root.receiving ? (root.state.visible === true ? "Visible to nearby Apple devices" : "Receiver on · waiting for visibility") : "Not discoverable"
                font.bold: true
            }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                visible: !!root.blocker
                text: root.blocker + (root.blocker.indexOf("channel") >= 0 ? "\nConnect Wi-Fi to an access point on channel 6, 44 or 149, then click Refresh. Your current connection has been preserved." : "")
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; visible: !!root.errorText; text: root.errorText; color: "#c04040" }
            GridLayout {
                Layout.fillWidth: true
                columns: root.compact ? 2 : 3
                Button {
                    Layout.fillWidth: true
                    text: action.running ? "Please wait…" : root.receiving ? "Stop receiving" : "Receive files"
                    enabled: !root.busy && root.statusChecked && (root.receiving || (root.checked && !root.blocker))
                    onClicked: root.run(root.receiving ? ["off"] : ["on", duration.currentValue])
                }
                ComboBox {
                    id: duration; Layout.fillWidth: true; enabled: !root.receiving && !root.busy
                    textRole: "label"; valueRole: "value"
                    model: [{label:"10 minutes", value:"10m"}, {label:"30 minutes", value:"30m"}, {label:"One file", value:"once"}]
                }
                Button { Layout.columnSpan: root.compact ? 2 : 1; text: "Refresh"; onClicked: root.refresh() }
            }
            Label {
                text: "Files from nearby devices are saved while receiving is on."
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            Label {
                visible: root.receiving
                text: typeof root.state.remaining === "number"
                    ? "Receiving ends in " + Math.max(1, Math.ceil(root.state.remaining / 60)) + " minutes"
                    : root.state.mode === "once" ? "Receiving stops after one file" : "Receiving is on until stopped"
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            Label { text: "Device: " + (root.state.name || "This computer"); Layout.fillWidth: true; elide: Text.ElideRight }
            RowLayout {
                Label { text: "Visible to" }
                ComboBox {
                    model: ["Everyone", "Contacts only"]
                    currentIndex: root.state.visibility === "contacts" ? 1 : 0
                    enabled: !root.busy
                    delegate: ItemDelegate {
                        required property string modelData
                        required property int index
                        width: parent.width
                        text: modelData
                        enabled: index === 0 || root.contactsConfigured
                    }
                    onActivated: {
                        if (currentIndex === 1 && !root.contactsConfigured) return;
                        root.run(["visibility", currentIndex === 1 ? "contacts" : "everyone"]);
                    }
                }
            }
            Label {
                visible: !root.contactsConfigured
                text: "Contacts only requires a configured Apple identity and known senders. Everyone works without an Apple identity."
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: root.state.dir || "Downloads"; Layout.fillWidth: true; elide: Text.ElideMiddle }
                Button { text: "Choose folder"; enabled: !root.busy; onClicked: root.run(["dir", "--pick"]) }
            }
            Label { text: "Nearby Apple devices"; font.bold: true }
            Radar {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: root.compact ? 200 : 260; Layout.preferredHeight: root.compact ? 200 : 260
                peers: root.peers; scanning: root.receiving && !root.blocker
                foreground: root.palette.text; muted: true
                onPeerClicked: mac => root.sendTo(mac)
            }
            Label {
                text: root.peers.length ? "Select a device to choose and send files." : "No devices discovered. Turn receiving on, then open AirDrop on the nearby Apple device."
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            Repeater {
                model: root.peers
                Button { Layout.fillWidth: true; required property var modelData; text: modelData.name || modelData.mac; enabled: !root.busy && !root.blocker; onClicked: root.sendTo(modelData.mac) }
            }
            Label { text: root.progressText; visible: !!text; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: "Omdrop by netmojo-systems · Owly radio"; opacity: 0.65; font.pixelSize: 11 }
        }
    }
}
