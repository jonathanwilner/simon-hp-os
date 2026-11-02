import QtQuick
import Quickshell
import Quickshell.Io
Item {
    id: root
    visible: false
    property bool settingsOnly: Quickshell.env("HP_OS_TOUCH_SETTINGS") === "1"
    property var config: ({})
    property var runtime: ({})
    property var inputState: ({active:false, available:false, secure:true, candidates:[]})
    property var visualPrefs: ({})
    property var policyPrefs: ({})
    property string shellAppearance:""
    property bool shellReducedMotion:false
    readonly property bool systemDark: shellAppearance==="dark" || (shellAppearance!=="light" && Qt.styleHints.colorScheme===Qt.Dark)
    readonly property var prefs: Object.assign({},config.keyboard ?? {},settingsOnly && config.keyboard?.mode!=="off" ? policyPrefs : {},visualPrefs)
    readonly property bool secure: inputState.secure !== false
    readonly property bool available: socket.connected && inputState.available === true
    readonly property bool active: available && (inputState.active === true || inputState.manual === true)
    readonly property bool gestureAvailable: !secure && inputState.gestureAvailable===true
    property bool traceMode:false
    property int clipboardSerial:0
    property bool initializedLanguage:false
    property var preferenceQueue:[]
    readonly property bool shown: runtime.visible === true && ["manual","tablet-only","always"].includes(prefs.mode) && prefs.backend !== "none"
    readonly property string language: inputState.language ?? "en_US"
    readonly property var candidates: secure ? [] : (inputState.candidates ?? [])
    readonly property string preedit: secure ? "" : (inputState.preedit ?? "")
    property bool shift: false
    property bool caps: false
    property double lastShift: 0
    property string layout: "letters"
    property bool settingsOpen: false
    property bool languagesOpen: false
    property bool cursorMode: false
    property string error: ""
    readonly property bool numeric: [2,3,4,9].includes(inputState.purpose)
    readonly property bool phone: inputState.purpose === 4
    readonly property string returnLabel: inputState.returnLabel || "Enter"
    readonly property var languages: prefs.languages ?? ["en_US", "zh_CN"]
    function send(message) {
        if (!active) return false
        socket.write(JSON.stringify(message) + "\n"); socket.flush(); return true
    }
    function feedback() { if(prefs.sound?.enable===true) { sound.command=["paplay",Qt.resolvedUrl("keypress.wav").toString().replace("file://","")]; sound.running=true } }
    function paste() { if(!secure && active) { clipboardSerial=inputState.serial; clipboard.running=true } }
    function text(value) {
        feedback()
        if (send({op:"text", text:value}) && shift && !caps) shift = false
    }
    function key(name, modifiers) { feedback(); send({op:"key",key:name,modifiers:modifiers ?? []}) }
    function letter(value) { text((shift || caps) ? value.toUpperCase() : value) }
    function setLanguage(value) { setting("language",value); send({op:"language",language:value}); languagesOpen = false; layout = "letters" }
    function cycleLanguage() { setLanguage(languages[(languages.indexOf(language)+1)%languages.length]) }
    function selectCandidate(index) { if (!secure) send({op:"candidate",index:index}) }
    function shiftPressed() {
        const now = Date.now()
        if (caps) { caps=false; shift=false }
        else if (now-lastShift < 360) { caps=true; shift=true }
        else shift = !shift
        lastShift=now
    }
    function command(args) { control.command=["touch-support"].concat(args); control.running=true }
    function hide() { command(["hide"]) }
    function setting(key, value) {
        visualPrefs=Object.assign({},visualPrefs,{[key]:value})
        preferenceQueue.push([key,value]); drainPreferences()
        if (key==="prediction") send({op:"prediction",enabled:value.enable===true})
    }
    function drainPreferences() {
        if(preferenceWriter.running || !preferenceQueue.length) return
        const entry=preferenceQueue.shift()
        preferenceWriter.command=["python3",Qt.resolvedUrl("preferences.py").toString().replace("file://",""),entry[0],JSON.stringify(entry[1])]
        preferenceWriter.running=true
    }
    function receive(line) {
        try {
            const state=JSON.parse(line)
            if (state.type === "state") {
                const previousSecure=secure
                inputState=state
                if(active && !initializedLanguage) { initializedLanguage=true; if(prefs.language)send({op:"language",language:prefs.language}); send({op:"prediction",enabled:prefs.prediction?.enable!==false}) }
                if (!(state.active || state.manual) || state.secure !== previousSecure) {
                    shift=false; caps=false; layout="letters"; settingsOpen=false; languagesOpen=false; traceMode=false
                }
            }
        } catch (_) { error="Invalid backend state" }
    }
    FileView {
        path:(Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME")+"/.local/state")+"/hp-os/appearance-mode"
        watchChanges:true; printErrors:false
        onFileChanged:reload()
        onLoaded:root.shellAppearance=text().trim()
    }
    FileView {
        path:(Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME")+"/.config")+"/illogical-impulse/config.json"
        watchChanges:true; printErrors:false
        onFileChanged:reload()
        onLoaded:{try{root.shellReducedMotion=JSON.parse(text()).hpos?.reducedMotion===true}catch(_) {}}
    }
    FileView {
        id: configuration
        path: Quickshell.env("HP_OS_TOUCH_CONFIG") || (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME")+"/.config")+"/hp-os/touch.json"
        watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: { try { root.config=JSON.parse(text()) } catch (_) { root.error="Invalid touch configuration" } }
        onLoadFailed: { if(path!=="/etc/hp-os/touch.json") path="/etc/hp-os/touch.json" }
    }
    FileView {
        path: Quickshell.env("HP_OS_TOUCH_STATE") || Quickshell.env("XDG_RUNTIME_DIR")+"/hp-os-touch/state.json"
        watchChanges:true; printErrors:false
        onFileChanged: reload()
        onLoaded: { try { root.runtime=JSON.parse(text()); if (root.runtime.config && !root.settingsOnly) root.config=root.runtime.config } catch (_) { root.runtime=({visible:false}) } }
    }
    Socket {
        id: socket
        path: Quickshell.env("HP_OS_TOUCH_INPUT_SOCKET") || Quickshell.env("XDG_RUNTIME_DIR")+"/hp-os-touch/input.sock"
        connected: !root.settingsOnly
        parser: SplitParser { onRead: data => root.receive(data) }
        onError: { socket.connected=false; if(!root.settingsOnly) reconnect.restart() }
        onConnectedChanged: {
            if (connected) { write('{"op":"status"}\n'); flush() }
            else if (!root.settingsOnly) { root.initializedLanguage=false; root.inputState=({active:false,available:false,secure:true,candidates:[]}); reconnect.restart() }
        }
    }
    Timer { id: reconnect; interval: 2500; onTriggered: { socket.connected=false; socket.connected=true } }
    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME")+"/.config")+"/hp-os/touch-ui/preferences.json"
        watchChanges:true; printErrors:false
        onFileChanged:reload()
        onLoaded: { try { root.visualPrefs=JSON.parse(text()); if(root.active && root.prefs.language && root.prefs.language!==root.language) root.send({op:"language",language:root.prefs.language}); if(root.active)root.send({op:"prediction",enabled:root.prefs.prediction?.enable!==false}) } catch (_) {} }
    }
    FileView {
        path:(Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME")+"/.config")+"/hp-os/touch-preferences.json"
        watchChanges:true; printErrors:false
        onFileChanged:reload()
        onLoaded:{try{root.policyPrefs=JSON.parse(text())}catch(_) {}}
    }
    Process { id:sound }
    Process {
        id:clipboard; command:["wl-paste","--no-newline"]
        stdout:StdioCollector { onStreamFinished: { if(!root.secure && root.active && root.inputState.serial===root.clipboardSerial) root.text(text) } }
    }
    Process { id: preferenceWriter; onExited:root.drainPreferences() }
    Process { id: control; stderr:StdioCollector { onStreamFinished:root.error=text.trim() } }
}
