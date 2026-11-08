import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell
import Quickshell.Io
import "IdentityFormat.js" as IdentityFormat

Frame {
    id: setup
    property string cli: ""
    property var identity: ({})
    property bool checked: false
    property bool receiving: false
    property bool externalBusy: false
    readonly property bool busy: operation.running
    property bool expanded: false
    property bool guideVisible: false
    property string resultText: ""
    property bool failed: false
    property string folderPurpose: "import"
    signal statusUpdated(var status)
    signal refreshRequested()

    function run(args) {
        if (busy || externalBusy) return;
        resultText = "";
        failed = false;
        operation.command = [cli].concat(args).concat(["--json"]);
        operation.running = true;
    }
    function choose(purpose) {
        folderPurpose = purpose;
        folders.title = purpose === "import" ? "Choose the folder containing your Apple identity files" : "Choose where to save the Mac helper";
        folders.open();
    }
    function expiry(value) {
        if (!value) return "Unknown";
        const parsed = new Date(value);
        return isNaN(parsed.getTime()) ? String(value) : Qt.formatDateTime(parsed, "d MMM yyyy");
    }
    FolderDialog {
        id: folders
        onAccepted: {
            const path = IdentityFormat.localPath(selectedFolder);
            if (!path) {
                setup.failed = true;
                setup.resultText = "Choose a local folder.";
                return;
            }
            setup.run([setup.folderPurpose, path]);
        }
    }
    Process {
        id: operation
        stdout: StdioCollector { onStreamFinished: {
            if (!text.trim()) return;
            try {
                const result = JSON.parse(text);
                setup.failed = result.ok === false;
                setup.resultText = result.message || (setup.failed ? "The action failed." : "Done.");
                if (result.status) setup.statusUpdated(result.status);
                else if (result.state !== undefined) setup.statusUpdated(result);
            } catch (e) {
                setup.failed = true;
                setup.resultText = "The identity tool returned an unreadable result.";
            }
        } }
        // The backend deliberately provides safe, user-facing errors in JSON.
        // Do not echo external tool output, which can contain account details.
        onExited: (code, exitStatus) => {
            if (code !== 0) {
                setup.failed = true;
                if (!setup.resultText) setup.resultText = "The identity tool could not finish. Check the setup guide and try again.";
            }
            setup.refreshRequested();
        }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Apple Account"; font.bold: true; Layout.fillWidth: true }
            Button {
                text: setup.expanded ? "Close setup" : "Set up"
                onClicked: setup.expanded = !setup.expanded
                Accessible.name: "Show Apple Account setup"
            }
        }
        Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: !setup.checked ? "Checking identity…" : setup.identity.message || "No Apple identity is configured."
        }
        Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            visible: setup.identity.source === "disk" && setup.identity.valid === true
            text: "Sending identity: Apple Account" + (setup.receiving && setup.identity.active_source !== "disk" ? " · restart receiving to use it" : "")
        }
        Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            visible: setup.identity.source === "self-signed"
            text: "Sending identity: basic. Nearby Apple recipients must select Everyone."
        }
        ColumnLayout {
            visible: setup.expanded
            Layout.fillWidth: true
            spacing: 10
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: "An Apple identity lets this computer send to Apple devices in Contacts Only when they recognize your account. OM Drop does not ask for your Apple Account password."
            }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                visible: !!setup.identity.record_expires || !!setup.identity.certificate_expires
                text: "Account record expires: " + setup.expiry(setup.identity.record_expires) + "\nCertificate expires: " + setup.expiry(setup.identity.certificate_expires)
            }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                visible: typeof setup.identity.days_remaining === "number" && setup.identity.days_remaining <= 7
                text: setup.identity.days_remaining <= 0 ? "The identity has expired. Import a newly issued identity before sending to Contacts Only." : "Renew soon: " + Math.ceil(setup.identity.days_remaining) + " day(s) remaining. Import a newly issued identity to renew it."
                font.bold: true
            }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                visible: setup.receiving
                text: "Stop receiving before importing or switching identity. Enable receiving again when setup is complete."
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Button { text: "Import identity folder"; enabled: !setup.busy && !setup.externalBusy && !setup.receiving; onClicked: setup.choose("import") }
                Button { text: "Check identity"; enabled: !setup.busy && !setup.externalBusy; onClicked: setup.run(["check"]) }
                Button { text: "Use basic identity"; enabled: !setup.busy && !setup.externalBusy && !setup.receiving && setup.identity.source !== "self-signed"; onClicked: setup.run(["use-self-signed"]) }
            }
            Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: "Import a folder containing certificate.pem, key.pem and validation_record.cms from the same account. Files are validated before installation. Basic identity keeps the Apple files for later use."
            }
            Button { text: setup.guideVisible ? "Hide setup guide" : "Setup guide"; onClicked: setup.guideVisible = !setup.guideVisible }
            ColumnLayout {
                visible: setup.guideVisible
                Layout.fillWidth: true
                spacing: 10
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "1. Obtain your identity\nUse an existing AirDrop identity export from your own Apple Account. Keep the three files private and transfer them through a trusted connection."
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "Advanced Mac helper\nThe included helper exports the signed-in Mac account. It uses private Apple permissions and works only on Macs already configured to allow them. Ordinary protected Macs may refuse the export. The helper does not change Mac security settings."
                }
                Button {
                    text: "Save Mac helper…"
                    enabled: !setup.busy && !setup.externalBusy
                    onClicked: setup.choose("export-helper")
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "This creates an omdrop-mac-helper folder at the selected location. Follow its instructions on the Mac. There is no general Apple Account sign-in or automatic certificate enrollment."
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "2. Import and check\nStop receiving, import the folder, then enable AirDrop again. Expiry status describes the local identity files. Re-exporting a cached record does not renew it; import a newly issued record before expiry."
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "3. Test Contacts Only\nFor different Apple Accounts, save the sending account’s email or phone number in the receiving Apple device’s Contacts. Select Contacts Only on that device, keep it awake nearby, and send a small file. Confirm the file arrives."
                }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: "Receiving on this computer\nOM Drop’s Contacts Only setting uses its own known-senders list. Importing your Apple identity does not populate that list or change who may send you files."
                }
            }
            Label {
                visible: setup.busy || !!setup.resultText
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: setup.busy ? "Working on identity…" : setup.resultText
                color: setup.failed ? "#c04040" : setup.palette.text
            }
        }
    }
}
