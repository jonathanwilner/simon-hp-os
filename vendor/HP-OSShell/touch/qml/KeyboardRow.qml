import QtQuick
Row {
    id:root
    required property var keys
    required property var controller
    required property var tokens
    spacing:tokens.gap
    property real weightTotal: keys.reduce((n,k)=>n+(k.weight??1),0)
    signal action(string name)
    Repeater {
        model:root.keys
        KeyboardKey {
            required property var modelData
            width:(root.width-root.spacing*(root.keys.length-1))*(modelData.weight??1)/root.weightTotal
            height:root.height; tokens:root.tokens
            label:modelData.action==="shift" && root.controller.caps?"⇪":modelData.label; alternate:modelData.alternate??""; accents:modelData.accents??""
            modifier:!!modelData.action; accent:modelData.action==="enter" || (modelData.action==="shift" && root.controller.shift)
            space:modelData.action==="space"
            cursorSwipe:!modelData.action
            wordDelete:modelData.action==="backspace"
            onDeleteWord:root.controller.key("BackSpace",["Control"])
            repeatable:["backspace","left","right"].includes(modelData.action)
            preview:!root.controller.secure && root.controller.prefs.keyPreview !== false
            enabledInput:root.controller.active
            z:held?10:0
            onActivated: value => { if (modelData.action) root.action(modelData.action); else root.controller.text(value) }
            onCursor: direction => root.controller.key(direction>0?"Right":"Left")
            onOptions: { if (modelData.action==="language" || modelData.action==="space") root.controller.languagesOpen=true }
        }
    }
}
