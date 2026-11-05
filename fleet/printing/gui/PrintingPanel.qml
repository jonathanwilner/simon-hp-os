import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell
import Quickshell.Io

Pane {
    id: root
    property bool compact: false
    property color errorColor: "#c04040"
    background: Rectangle { color: root.palette.window; radius: root.compact ? 16 : 0 }
    padding: compact ? 12 : 18
    property string cli: "@client@/bin/hp-os-aware-print"
    property var printers: []
    property string peer: ""
    property string documentPath: ""
    property string secretPath: ""
    property string message: "Checking the printing radio…"
    property string diagnostic: ""
    property bool ready: false
    property bool failed: false
    property bool responseReceived: false
    property string operation: "doctor"
    readonly property bool busy: worker.running
    function localPath(url) { return decodeURIComponent(url.toString().replace(/^file:\/\//, "")); }
    function start(command) {
        if (busy) return;
        operation = command[0]; failed = false; responseReceived = false;
        message = operation === "discover" ? "Looking for nearby printers…" : operation === "print" ? "Connecting and sending the document. Waiting for the printer to confirm completion…" : "Checking the printing radio…";
        worker.command = [cli].concat(command); worker.running = true;
    }
    function printDocument() {
        var args = ["print", "--peer", peer, "--file", documentPath, "--service", secure.checked ? "_ipps._tcp" : "_ipp._tcp"];
        if (openConnection.checked) args.push("--allow-open");
        else args.push("--passphrase-file", secretPath);
        if (secure.checked && pin.text.trim()) args.push("--cert-sha256", pin.text.trim());
        start(args);
    }
    Component.onCompleted: start(["doctor"])
    Process {
        id: worker
        stdout: StdioCollector { onStreamFinished: {
            try {
                var result = JSON.parse(text);
                root.responseReceived = true;
                root.failed = result.ok !== true;
                if (root.failed) {
                    root.message = result.error || "The operation failed.";
                    if (root.operation === "doctor") { root.ready = false; root.diagnostic = root.message + "\n" + (result.hint || ""); root.message = "Set up a dedicated Wi-Fi Aware adapter to find nearby printers. Your existing Wi-Fi connection stays active."; }
                } else if (root.operation === "doctor") {
                    root.ready = result.data_interface_present === true && /(^|\n)nan_started=1(\n|$)/.test(result.nan_status || "");
                    root.message = root.ready ? "Printing radio is available. Find a compatible nearby printer." : "The dedicated printing radio has not started.";
                    root.diagnostic = result.nan_status || "";
                } else if (root.operation === "discover") {
                    root.printers = result.printers || []; root.peer = "";
                    root.message = root.printers.length ? "Select a printer below." : "No compatible printers found. Keep the printer nearby and enable its Wi-Fi Aware service.";
                } else root.message = "Printer confirmed completion. Job " + result.job_id + ".";
            } catch (e) { root.failed = true; root.message = "The printing service returned an unreadable response."; }
        } }
        onExited: (code, exitStatus) => Qt.callLater(function() {
            if (!root.responseReceived) {
                root.failed = true;
                root.message = root.operation === "print" ? "The printing service stopped before confirming completion. Check the printer before sending again." : "The printing service did not respond. Check radio details and try again.";
                if (root.operation === "doctor") root.ready = false;
            }
        })
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) root.diagnostic = text.trim(); } }
    }
    FileDialog { id: documentPicker; title: "Choose a document"; nameFilters: ["Printable documents (*.pdf *.jpg *.jpeg)"]; onAccepted: root.documentPath = root.localPath(selectedFile) }
    FileDialog { id: secretPicker; title: "Choose the private printer passphrase file"; onAccepted: root.secretPath = root.localPath(selectedFile) }
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 12
            Label { visible: !root.compact; text: "Nearby printing"; font.pixelSize: root.compact ? 20 : 24; font.bold: true }
            Label { Layout.fillWidth: true; text: "Wi-Fi Aware · Direct to printer"; opacity: 0.65 }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Print PDF and JPEG documents through a compatible printer’s Wi-Fi Aware service." }
            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    width: parent.width
                    Label { text: root.ready ? "Printing radio available" : "Printing radio setup"; font.bold: true }
                    Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: root.message; color: root.failed && root.operation !== "doctor" ? root.errorColor : palette.text }
                    BusyIndicator { running: root.busy; visible: running; Layout.alignment: Qt.AlignHCenter }
                    RowLayout {
                        Button { text: "Check radio"; enabled: !root.busy; onClicked: root.start(["doctor"]) }
                        Button { text: "Find printers"; enabled: root.ready && !root.busy; onClicked: root.start(["discover", "--service", secure.checked ? "_ipps._tcp" : "_ipp._tcp"]) }
                    }
                }
            }
            Label { text: "Nearby printers"; font.bold: true }
            Repeater {
                model: root.printers
                delegate: RadioButton {
                    id: printerChoice
                    required property var modelData
                    Layout.fillWidth: true
                    contentItem: ColumnLayout {
                        spacing: 3
                        Label {
                            Layout.fillWidth: true
                            leftPadding: printerChoice.indicator.width + printerChoice.spacing
                            text: printerChoice.modelData.name || "Printer"
                            wrapMode: Text.WrapAnywhere
                            font.bold: printerChoice.checked
                        }
                        Label {
                            Layout.fillWidth: true
                            leftPadding: printerChoice.indicator.width + printerChoice.spacing
                            text: printerChoice.modelData.address
                            opacity: 0.65
                            font.pixelSize: 12
                        }
                    }
                    checked: root.peer === modelData.address
                    enabled: !root.busy
                    onClicked: root.peer = modelData.address
                }
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; visible: root.printers.length === 0; text: "Search to discover compatible printers."; opacity: 0.65 }
            Button { text: root.documentPath ? "Change document" : "Choose PDF or JPEG"; enabled: !root.busy; onClicked: documentPicker.open() }
            Label { Layout.fillWidth: true; visible: !!root.documentPath; text: root.documentPath; elide: Text.ElideMiddle }
            Button {
                id: connectionSettings
                text: checked ? "Connection settings ▴" : "Connection settings ▾"
                checkable: true
                enabled: !root.busy
            }
            Frame {
                Layout.fillWidth: true
                visible: connectionSettings.checked
                ColumnLayout {
                    width: parent.width
                    spacing: 10
            CheckBox { id: openConnection; text: "Use an open printer connection"; enabled: !root.busy }
            Button { visible: !openConnection.checked; text: root.secretPath ? "Change passphrase file" : "Choose private passphrase file"; enabled: !root.busy; onClicked: secretPicker.open() }
            Label { Layout.fillWidth: true; visible: !openConnection.checked; wrapMode: Text.WordWrap; opacity: 0.65; text: root.secretPath ? root.secretPath : "Use a file readable only by your account. The passphrase is never displayed." }
            CheckBox { id: secure; text: "Encrypted IPPS service"; enabled: !root.busy; onToggled: { root.printers = []; root.peer = ""; } }
            TextField { id: pin; Layout.fillWidth: true; visible: secure.checked; enabled: !root.busy; placeholderText: "Optional trusted certificate SHA-256"; maximumLength: 64 }
            Label { Layout.fillWidth: true; visible: secure.checked; wrapMode: Text.WordWrap; opacity: 0.65; text: "Leave blank for normal certificate verification. Only enter a fingerprint verified with the printer owner." }
                }
            }
            Label {
                Layout.fillWidth: true
                visible: !!root.peer && !openConnection.checked && !root.secretPath
                wrapMode: Text.WordWrap
                text: "Open Connection settings to choose a passphrase file or allow an open connection."
                opacity: 0.65
            }
            Button {
                text: "Print document"
                highlighted: true
                enabled: root.ready && !root.busy && !!root.peer && !!root.documentPath && (openConnection.checked || !!root.secretPath) && (!secure.checked || !pin.text.trim() || /^[0-9a-fA-F]{64}$/.test(pin.text.trim()))
                onClicked: root.printDocument()
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; opacity: 0.65; text: "If completion cannot be confirmed, check the printer before sending again. Your existing Wi-Fi connection stays active." }
            Button { id: details; text: checked ? "Hide radio details" : "Show radio details"; checkable: true }
            Label { Layout.fillWidth: true; visible: details.checked; wrapMode: Text.WrapAnywhere; text: root.diagnostic || "No additional details."; font.pixelSize: 12 }
        }
    }
}
