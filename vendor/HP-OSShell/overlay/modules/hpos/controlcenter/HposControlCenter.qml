pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth
import Quickshell.Services.UPower
import qs
import qs.services
import qs.modules.common
import qs.modules.common.models.quickToggles
import qs.modules.common.widgets
import qs.modules.iris.components
import qs.modules.iris.style
import qs.modules.hpos.design

// PC composition; services and detail lists remain owned by iNiR.
ColumnLayout {
    id: root
    property var touchPolicy: ({})
    FileView {
        id: touchConfiguration
        path: Quickshell.env("HP_OS_TOUCH_CONFIG") || (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/hp-os/touch.json"
        watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: { try { root.touchPolicy = JSON.parse(text()) } catch (_) { root.touchPolicy = ({}) } }
        onLoadFailed: { if (path !== "/etc/hp-os/touch.json") path = "/etc/hp-os/touch.json" }
    }
    Process { id: touchToggle; command: ["touch-support", "toggle"] }
    property var targetScreen: null
    property string picker: ""
    property bool editing: false
    readonly property real d: IrisStyle.density
    readonly property var monitor: Brightness.getMonitorForScreen(targetScreen)
    readonly property var defaults: ["focus", "darkMode", "nightLight", "profiles", "mic", "idle", "snip", "lock", "settings", "session"]
    readonly property var actions: {
        Config.revision
        const saved = Config.options?.hpos?.controlCenter?.actions
        // JsonObject list<string> is a QML sequence, not necessarily a JS Array.
        const list = saved !== null && saved !== undefined && typeof saved.length === "number" ? Array.from(saved) : root.defaults.slice()
        return list.filter((id, index) => root.defaults.includes(id) && list.indexOf(id) === index)
    }
    spacing: 12 * d
    function focusInitial() { editButton.forceActiveFocus() }
    onVisibleChanged: if (visible) { root.monitor?.refresh(); hotspot.refreshStatus() }
    Keys.onEscapePressed: event => { root.picker = ""; root.editing = false; GlobalStates.controlPanelOpen = false; event.accepted = true }
    function togglePicker(name) { picker = picker === name ? "" : name }
    function takePickerRequest() {
        const next = GlobalStates.irisControlPickerRequest
        if (!next.length) return
        picker = next === "none" ? "" : next
        GlobalStates.irisControlPickerRequest = ""
    }
    Component.onCompleted: takePickerRequest()
    Connections {
        target: GlobalStates
        function onIrisControlPickerRequestChanged() { root.takePickerRequest() }
    }
    function saveActions(list) { Config.setNestedValue("hpos.controlCenter.actions", list) }
    function moveAction(index, step) {
        const next = root.actions.slice()
        const destination = index + step
        if (destination < 0 || destination >= next.length) return
        const item = next.splice(index, 1)[0]
        next.splice(destination, 0, item)
        root.saveActions(next)
    }
    property string actionError: ""
    property int requestedWifi: -1
    readonly property var bluetoothAdapter: Bluetooth.defaultAdapter
    readonly property bool bluetoothConfirmed: bluetoothAdapter?.state === BluetoothAdapterState.Enabled
    property int requestedBluetooth: -1
    property int requestedHotspot: -1
    Connections {
        target: Network
        function onWifiEnabledChanged() {
            if (Number(Network.wifiEnabled) === root.requestedWifi) { root.requestedWifi = -1; wifiTimeout.stop() }
        }
    }
    Connections {
        target: root.bluetoothAdapter
        ignoreUnknownSignals: true
        function onStateChanged() {
            const actual = root.bluetoothAdapter?.state
            if ((root.requestedBluetooth === 1 && actual === BluetoothAdapterState.Enabled)
                || (root.requestedBluetooth === 0 && actual === BluetoothAdapterState.Disabled)) {
                root.requestedBluetooth = -1
                bluetoothTimeout.stop()
            }
        }
    }
    function toggleConnection(model) {
        if (model === network) { root.toggleNetwork(); return }
        root.actionError = ""
        if (model === bluetooth) {
            if (!root.bluetoothAdapter || root.requestedBluetooth >= 0) return
            root.requestedBluetooth = root.bluetoothConfirmed ? 0 : 1
            bluetoothTimeout.restart()
            root.bluetoothAdapter.enabled = root.requestedBluetooth === 1
        } else if (model === hotspot) {
            if (root.requestedHotspot >= 0) return
            root.requestedHotspot = hotspot.toggled ? 0 : 1
            hotspotTimeout.restart()
            hotspot.mainAction()
        } else if (model !== vpn || !Vpn.busy) model.mainAction()
    }
    Timer {
        id: bluetoothTimeout
        interval: 8000
        onTriggered: {
            if (root.requestedBluetooth >= 0 && !((root.requestedBluetooth === 1 && root.bluetoothConfirmed)
                || (root.requestedBluetooth === 0 && root.bluetoothAdapter?.state === BluetoothAdapterState.Disabled)))
                root.actionError = HposTokens.tr("Bluetooth did not confirm the requested state. Check adapter permissions or radio blocking.", "蓝牙未确认请求状态，请检查适配器权限或无线设备锁定。")
            root.requestedBluetooth = -1
        }
    }
    Timer {
        id: hotspotTimeout
        interval: 15000
        onTriggered: {
            if (root.requestedHotspot >= 0 && Number(hotspot.toggled) !== root.requestedHotspot)
                root.actionError = HposTokens.tr("Hotspot did not confirm the requested state. Check network settings.", "热点未确认请求状态，请检查网络设置。")
            root.requestedHotspot = -1
        }
    }
    function toggleNetwork() {
        if (root.requestedWifi >= 0) return
        root.actionError = ""
        root.requestedWifi = Network.wifiEnabled ? 0 : 1
        wifiTimeout.restart()
        network.mainAction()
    }
    Timer {
        id: wifiTimeout
        interval: 8000
        onTriggered: {
            if (root.requestedWifi >= 0 && Number(Network.wifiEnabled) !== root.requestedWifi)
                root.actionError = HposTokens.tr("Wi-Fi did not reach the requested state. Check network settings.", "无线网络未达到请求状态，请检查网络设置。")
            root.requestedWifi = -1
        }
    }
    NetworkToggle { id: network }
    BluetoothToggle { id: bluetooth }
    HotspotToggle {
        id: hotspot
        onToggledChanged: if (Number(toggled) === root.requestedHotspot) { root.requestedHotspot = -1; hotspotTimeout.stop() }
    }
    VpnToggle { id: vpn }
    NotificationToggle { id: focus }
    NightLightToggle { id: nightLight }
    PowerProfilesToggle { id: profiles }
    MicToggle { id: microphone }
    IdleInhibitorToggle { id: idle }
    ScreenSnipToggle { id: snip }
    function modelFor(id) {
        return ({ focus: focus, nightLight: nightLight, profiles: profiles, mic: microphone, idle: idle, snip: snip })[id] ?? null
    }
    function titleFor(id) {
        return ({focus: HposTokens.tr("Do Not Disturb", "勿扰模式"), profiles: HposTokens.tr("Power mode", "电源模式"), mic: HposTokens.tr("Microphone", "麦克风"), darkMode: HposTokens.tr("Dark mode", "深色模式"), lock: Translation.tr("Lock"), settings: Translation.tr("Settings"), session: Translation.tr("Session")})[id] ?? modelFor(id)?.name ?? id
    }
    function iconFor(id) {
        return ({focus: "notifications_off", darkMode: "dark_mode", lock: "lock", settings: "settings", session: "power_settings_new"})[id] ?? modelFor(id)?.icon ?? "circle"
    }
    function activate(id) {
        if (id === "darkMode") HposTokens.setPreference("appearance", HposTokens.dark ? "light" : "dark")
        else if (id === "lock") {
            GlobalStates.controlPanelOpen = false
            GlobalStates.screenLocked = true
        } else if (id === "settings") { GlobalStates.controlPanelOpen = false; GlobalStates.openSettings() }
        else if (id === "session") { GlobalStates.controlPanelOpen = false; GlobalStates.sessionOpen = true }
        else {
            if (id === "snip") GlobalStates.controlPanelOpen = false
            modelFor(id)?.mainAction()
        }
    }
    RowLayout {
        Layout.fillWidth: true
        IrisText { Layout.fillWidth: true; text: HposTokens.tr("Control Center", "控制中心"); role: IrisText.Title }
        IrisIconButton {
            id: editButton
            activeFocusOnTab: true
            materialIcon: root.editing ? "done" : "edit"
            Accessible.name: root.editing ? Translation.tr("Done") : Translation.tr("Arrange the controls")
            onClicked: root.editing = !root.editing
        }
    }
    IrisText {
        Layout.fillWidth: true
        visible: root.actionError.length > 0
        text: root.actionError
        color: IrisStyle.danger
        wrapMode: Text.WordWrap
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2
        rowSpacing: 8 * root.d
        columnSpacing: 8 * root.d
        ConnectionCard { model: network; detailPage: "network" }
        ConnectionCard { model: bluetooth; detailPage: "bluetooth" }
        ConnectionCard { model: hotspot; detailPage: "network" }
        ConnectionCard { model: vpn; detailPage: "network" }
    }
    IrisText {
        Layout.fillWidth: true
        visible: Network.ethernet
        text: HposTokens.tr("Ethernet connected", "以太网已连接")
        font.pixelSize: IrisStyle.typeCaption
        color: IrisStyle.subtext
    }
    IrisText {
        Layout.fillWidth: true
        visible: Vpn.lastError.length > 0
        text: Vpn.errorText || Vpn.lastError
        wrapMode: Text.WordWrap
        color: IrisStyle.danger
    }
    IrisMediaCard {
        Layout.fillWidth: true
        compact: true
        showPlayers: false
        active: root.visible
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 6 * root.d
        Level { kind: "brightness" }
        IrisIconButton {
            visible: root.touchPolicy.enable === true && root.touchPolicy.keyboard?.mode !== "off" && root.touchPolicy.keyboard?.backend !== "none" && root.touchPolicy.keyboard?.showPanelButton !== false
            materialIcon: "keyboard"
            Accessible.name: HposTokens.tr("Toggle touch keyboard", "切换触控键盘")
            onClicked: { GlobalStates.controlPanelOpen = false; touchToggle.running = true }
        }
        IrisIconButton { materialIcon: "display_settings"; Accessible.name: Translation.tr("Display"); onClicked: root.togglePicker("display") }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 6 * root.d
        Level { kind: "volume" }
        IrisIconButton { materialIcon: "speaker_group"; Accessible.name: Translation.tr("Audio devices"); onClicked: root.togglePicker("devices") }
    }
    IrisText {
        Layout.fillWidth: true
        visible: Boolean(root.monitor?.writePending) || Number(root.monitor?._writeFailures ?? 0) > 3
        text: Number(root.monitor?._writeFailures ?? 0) > 3
            ? HposTokens.tr("Brightness change failed. Check display permissions.", "亮度更改失败，请检查显示权限。")
            : HposTokens.tr("Applying requested brightness…", "正在应用请求的亮度…")
        color: Number(root.monitor?._writeFailures ?? 0) > 3 ? IrisStyle.danger : IrisStyle.subtext
        wrapMode: Text.WordWrap
    }
    // A single loader keeps inactive detail lists and their delegates out of the scene.
    Loader {
        Layout.fillWidth: true
        active: root.picker.length > 0 && root.picker !== "power"
        sourceComponent: root.picker === "network" ? networkDetails : root.picker === "bluetooth" ? bluetoothDetails
            : root.picker === "display" ? displayDetails : root.picker === "system" ? systemDetails : audioDetails
    }
    Component { id: networkDetails; IrisNetworkList {} }
    Component { id: bluetoothDetails; IrisBluetoothList {} }
    Component { id: displayDetails; IrisDisplayList { targetScreen: root.targetScreen } }
    Component { id: systemDetails; IrisSystemList {} }
    Component { id: audioDetails; IrisDeviceList {} }
    ColumnLayout {
        Layout.fillWidth: true
        visible: !root.editing && root.actions.includes("profiles")
        spacing: 6 * root.d
        // HP-OS control-center features expose one tile with a detail view.
        // The three choices here reflect the native Linux PowerProfiles service.
        IrisButton {
            id: powerModeButton
            Layout.fillWidth: true
            implicitHeight: 54 * root.d
            selected: root.picker === "power"
            activeFocusOnTab: true
            Accessible.name: HposTokens.tr("Power mode", "电源模式") + ": " + powerModeLabel.text
            onClicked: root.togglePicker("power")
            RowLayout {
                anchors.fill: parent
                anchors.margins: 12 * root.d
                spacing: 10 * root.d
                MaterialSymbol {
                    text: PowerProfiles.profile === PowerProfile.PowerSaver ? "energy_savings_leaf"
                        : PowerProfiles.profile === PowerProfile.Performance ? "speed" : "balance"
                    iconSize: 24 * root.d
                    color: powerModeButton.foreground
                }
                IrisText {
                    Layout.fillWidth: true
                    text: HposTokens.tr("Power mode", "电源模式")
                    color: powerModeButton.foreground
                }
                IrisText {
                    id: powerModeLabel
                    text: PowerProfiles.profile === PowerProfile.PowerSaver ? HposTokens.tr("Power Saver", "节能")
                        : PowerProfiles.profile === PowerProfile.Performance ? HposTokens.tr("Performance", "性能")
                        : HposTokens.tr("Balanced", "均衡")
                    color: powerModeButton.foreground
                }
                MaterialSymbol {
                    text: root.picker === "power" ? "expand_less" : "expand_more"
                    iconSize: 20 * root.d
                    color: powerModeButton.foreground
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.picker === "power"
            spacing: 4 * root.d
            Repeater {
                model: [
                    { profile: PowerProfile.PowerSaver, icon: "energy_savings_leaf", label: HposTokens.tr("Power Saver", "节能"), detail: HposTokens.tr("Reduce power use for longer battery life.", "降低功耗，延长续航。") },
                    { profile: PowerProfile.Balanced, icon: "balance", label: HposTokens.tr("Balanced", "均衡"), detail: HposTokens.tr("Adjust performance to your workload and power source.", "根据工作负载和电源调整性能。") },
                    { profile: PowerProfile.Performance, icon: "speed", label: HposTokens.tr("Performance", "性能"), detail: HposTokens.tr("Prioritize performance with higher power use.", "优先提供性能，耗电量较高。") }
                ]
                IrisButton {
                    id: modeButton
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 42 * root.d
                    visible: modelData.profile !== PowerProfile.Performance || PowerProfiles.hasPerformanceProfile
                    selected: PowerProfiles.profile === modelData.profile
                    activeFocusOnTab: true
                    Accessible.name: modelData.label
                    Accessible.description: modelData.detail
                    Accessible.role: Accessible.RadioButton
                    Accessible.checkable: true
                    Accessible.checked: selected
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: modelData.detail
                    onClicked: {
                        PowerProfiles.profile = modelData.profile
                        root.picker = ""
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10 * root.d
                        spacing: 10 * root.d
                        MaterialSymbol {
                            text: modeButton.modelData.icon
                            iconSize: 22 * root.d
                            fill: modeButton.selected ? 1 : 0
                            color: modeButton.foreground
                        }
                        IrisText {
                            Layout.fillWidth: true
                            text: modeButton.modelData.label
                            font.weight: modeButton.selected ? Font.DemiBold : Font.Medium
                            color: modeButton.foreground
                        }
                        MaterialSymbol {
                            text: "check"
                            visible: modeButton.selected
                            iconSize: 20 * root.d
                            color: modeButton.foreground
                        }
                    }
                }
            }
        }
    }
    GridLayout {
        Layout.fillWidth: true
        visible: !root.editing
        columns: root.width >= 300 * root.d ? 5 : 4
        rowSpacing: 14 * root.d
        columnSpacing: 4 * root.d
        Repeater {
            model: root.actions.filter(id => id !== "profiles")
            ColumnLayout {
                id: action
                required property string modelData
                readonly property var control: root.modelFor(modelData)
                readonly property bool on: modelData === "darkMode" ? HposTokens.dark : modelData === "focus" ? Notifications.silent : Boolean(control?.toggled ?? false)
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: 5 * root.d
                IrisIconButton {
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 48 * root.d
                    implicitHeight: 48 * root.d
                    buttonRadius: height / 2
                    materialIcon: root.iconFor(action.modelData)
                    enabled: action.control?.available ?? true
                    colBackground: action.on ? IrisStyle.accent : IrisStyle.fillQuiet
                    colBackgroundHover: action.on ? IrisStyle.accent : IrisStyle.fillHover
                    foreground: action.on ? IrisStyle.inkOnAccent : IrisStyle.text
                    Accessible.name: root.titleFor(action.modelData)
                    Accessible.checkable: ["focus", "darkMode", "nightLight", "mic", "idle"].includes(action.modelData)
                    Accessible.checked: action.on
                    onClicked: root.activate(action.modelData)
                }
                IrisText {
                    Layout.fillWidth: true
                    text: root.titleFor(action.modelData)
                    font.pixelSize: IrisStyle.typeCaption
                    Layout.preferredHeight: Math.ceil(IrisStyle.typeCaption * 2.7)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignTop
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: root.editing
        IrisText { Layout.fillWidth: true; text: HposTokens.tr("Choose and reorder quick actions", "选择和排列快捷操作"); wrapMode: Text.WordWrap }
        Repeater {
            model: root.actions
            RowLayout {
                id: editRow
                required property string modelData
                required property int index
                Layout.fillWidth: true
                IrisText { Layout.fillWidth: true; text: root.titleFor(editRow.modelData) }
                IrisIconButton { materialIcon: "arrow_upward"; enabled: editRow.index > 0; Accessible.name: Translation.tr("Move up"); onClicked: root.moveAction(editRow.index, -1) }
                IrisIconButton { materialIcon: "arrow_downward"; enabled: editRow.index < root.actions.length - 1; Accessible.name: Translation.tr("Move down"); onClicked: root.moveAction(editRow.index, 1) }
                IrisIconButton { materialIcon: "remove"; Accessible.name: Translation.tr("Remove"); onClicked: root.saveActions(root.actions.filter(id => id !== editRow.modelData)) }
            }
        }
        Repeater {
            model: root.defaults.filter(id => !root.actions.includes(id))
            IrisButton {
                required property string modelData
                Layout.fillWidth: true
                text: "+ " + root.titleFor(modelData)
                onClicked: root.saveActions(root.actions.concat([modelData]))
            }
        }
    }
    component ConnectionCard: IrisButton {
        id: card
        required property var model
        readonly property bool lit: model === network ? Network.wifiEnabled : model === bluetooth ? root.bluetoothConfirmed : model.toggled
        readonly property bool pending: model === network ? root.requestedWifi >= 0
            : model === bluetooth ? root.requestedBluetooth >= 0
            : model === hotspot ? root.requestedHotspot >= 0 : model === vpn && Vpn.busy
        readonly property string label: model === network ? "WLAN" : model.name
        readonly property string detail: pending ? HposTokens.tr("Applying…", "正在应用…")
            : model === network ? (!Network.wifiCapabilityKnown ? HposTokens.tr("Checking adapter…", "正在检查适配器…")
                : !Network.wifiAvailable ? HposTokens.tr("No Wi-Fi adapter", "无无线网络适配器")
                : !Network.wifiEnabled ? Translation.tr("Off") : Network.active?.ssid || (["connected", "limited"].includes(Network.wifiStatus) ? Translation.tr("Connected") : Translation.tr("Not connected")))
            : model === bluetooth ? !root.bluetoothAdapter ? HposTokens.tr("No adapter", "无适配器")
                : root.bluetoothConfirmed ? model.statusText : root.bluetoothAdapter.state === BluetoothAdapterState.Disabled ? Translation.tr("Off") : HposTokens.tr("State unconfirmed", "状态未确认")
            : model === vpn ? Vpn.busy ? HposTokens.tr("Connecting…", "正在连接…") : Vpn.lastError.length ? Translation.tr("Connection failed") : model.statusText || Translation.tr("Off")
            : model.statusText
        readonly property string glyph: model === network ? Network.wifiEnabled ? "wifi" : "wifi_off"
            : model === bluetooth ? root.bluetoothConfirmed ? "bluetooth" : "bluetooth_disabled" : model.icon
        activeFocusOnTab: true
        property string detailPage: ""
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: 66 * root.d
        buttonRadius: 16 * root.d
        enabled: model === network || model === hotspot ? Network.wifiCapabilityKnown && Network.wifiAvailable : model.available
        colBackground: IrisStyle.fillQuiet
        colBackgroundHover: IrisStyle.fillHover
        Accessible.name: card.label + ": " + card.detail
        onClicked: root.togglePicker(detailPage)
        altAction: () => { if (!card.pending) root.toggleConnection(card.model) }
        RowLayout {
            anchors.fill: parent
            anchors.margins: 10 * root.d
            spacing: 8 * root.d
            IrisIconButton {
                implicitWidth: 38 * root.d
                implicitHeight: 38 * root.d
                buttonRadius: height / 2
                colBackground: card.lit ? IrisStyle.accent : IrisStyle.fill
                colBackgroundHover: card.lit ? IrisStyle.accent : IrisStyle.fillHover
                materialIcon: card.glyph
                enabled: !card.pending
                foreground: card.lit ? IrisStyle.inkOnAccent : IrisStyle.text
                Accessible.name: card.label
                Accessible.checkable: true
                Accessible.checked: card.lit
                onClicked: root.toggleConnection(card.model)
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2 * root.d
                IrisText { Layout.fillWidth: true; text: card.label; font.pixelSize: IrisStyle.typeLabel; color: IrisStyle.text; elide: Text.ElideRight }
                IrisText { Layout.fillWidth: true; text: card.detail; font.pixelSize: IrisStyle.typeCaption; color: IrisStyle.subtext; elide: Text.ElideRight }
            }
        }
    }
    component Level: IrisCapsuleSlider {
        id: level
        required property string kind
        Layout.fillWidth: true
        implicitHeight: 42 * root.d
        readonly property bool brightness: kind === "brightness"
        readonly property bool ready: brightness ? Boolean(root.monitor?.ready) && Number.isFinite(Number(root.monitor?.brightness)) : Audio.sink !== null
        enabled: ready
        opacity: ready ? 1 : 0.4
        vertical: false
        activeFocusOnTab: true
        Keys.onPressed: event => {
            if (!level.enabled) return
            let next = level.value
            if (event.key === Qt.Key_Left || event.key === Qt.Key_Down) next = Math.max(0, next - 0.05)
            else if (event.key === Qt.Key_Right || event.key === Qt.Key_Up) next = Math.min(1, next + 0.05)
            else if (event.key === Qt.Key_Home) next = 0
            else if (event.key === Qt.Key_End) next = 1
            else return
            level.moved(next)
            event.accepted = true
        }
        Rectangle { anchors.fill: parent; radius: height / 2; color: "transparent"; border.width: level.activeFocus ? 2 : 0; border.color: IrisStyle.accent }
        readout: true
        fillColor: HposTokens.dark ? "#586577" : "#dce2ed"
        filledForeground: HposTokens.text
        muted: !brightness && (Audio.sink?.audio?.muted ?? false)
        icon: brightness ? "light_mode" : muted ? "volume_off" : "volume_up"
        value: ready ? brightness ? root.monitor.brightness : Math.min(1, Audio.value ?? 0) : 0
        Accessible.onIncreaseAction: if (enabled) moved(Math.min(1, value + 0.05))
        Accessible.onDecreaseAction: if (enabled) moved(Math.max(0, value - 0.05))
        Accessible.name: brightness ? Translation.tr("Brightness") : Translation.tr("Volume")
        onMoved: next => { if (brightness) root.monitor?.setBrightness(next); else Audio.setSinkVolume(next) }
        onIconClicked: if (!brightness) Audio.toggleMute()
    }
}
