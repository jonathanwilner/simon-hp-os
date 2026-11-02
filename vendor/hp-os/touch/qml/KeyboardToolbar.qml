import QtQuick
Row {
    id:root; required property var controller; required property var tokens; spacing:8
    property var shortcuts: (controller.prefs.toolbar??["emoji","floating","cursor","settings"]).slice(0,4)
    function label(name) { return ({emoji:"☺",floating:"▣",cursor:"↔",settings:"⚙",language:"中 / En",symbols:"123",clipboard:"Paste",trace:"Trace"})[name]??name }
    function activate(name) {
        if (name==="emoji") controller.layout=controller.layout==="emoji"?"letters":"emoji"
        else if (name==="floating") controller.setting("floating",{active:!(controller.prefs.floating?.active??false)})
        else if (name==="cursor") controller.cursorMode=!controller.cursorMode
        else if (name==="settings") controller.settingsOpen=!controller.settingsOpen
        else if (name==="language") controller.languagesOpen=!controller.languagesOpen
        else if (name==="clipboard") controller.paste()
        else if (name==="trace" && controller.gestureAvailable) controller.traceMode=!controller.traceMode
        else if (name==="symbols") controller.layout=controller.layout==="symbols"?"letters":"symbols"
    }
    Repeater { model:root.shortcuts
        KeyboardKey { required property string modelData; tokens:root.tokens; width:52; height:40; label:root.label(modelData); modifier:true; preview:false; onActivated:root.activate(modelData) }
    }
    Item { width:Math.max(0,root.width-root.shortcuts.length*60-60); height:40 }
    KeyboardKey { tokens:root.tokens; width:52; height:40; label:"⌄"; modifier:true; preview:false; onActivated:controller.hide() }
}
