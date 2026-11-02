import QtQuick
import Quickshell
Flickable {
    id:root; required property var controller; required property var tokens
    clip:true; contentHeight:body.implicitHeight; boundsBehavior:Flickable.StopAtBounds
    Column { id:body; width:root.width; spacing:8
    Text { text:"Touch & Keyboard"; font.pixelSize:20; font.family:tokens.font; color:tokens.text }
    Text { width:parent.width; wrapMode:Text.Wrap; text:"Profile: "+(controller.config.profile??"laptop")+" · Posture: "+(controller.runtime.posture??"unknown")+" · Mode: "+(controller.prefs.mode??"off")+"\nBackend: "+(controller.runtime.visible?controller.runtime.backend??controller.prefs.backend:controller.prefs.backend??"hp-os-qml")+" · Input: "+(controller.active?"ready":"waiting for compatible field"); font.pixelSize:13; color:tokens.secondary }
    Text { width:parent.width; visible:controller.error.length>0; text:controller.error; wrapMode:Text.Wrap; color:tokens.secondary; font.pixelSize:12 }
    Flow { width:parent.width; spacing:8
        Repeater { model:["system","light","dark"]
            KeyboardKey { required property string modelData; width:96; height:42; tokens:root.tokens; label:modelData; accent:controller.prefs.colorScheme===modelData; preview:false; onActivated:controller.setting("colorScheme",modelData) }
        }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:110; height:42; tokens:root.tokens; label:"Smaller"; preview:false; onActivated:controller.setting("height",Math.max(330,(controller.prefs.height??360)-24)) }
        KeyboardKey { width:110; height:42; tokens:root.tokens; label:"Larger"; preview:false; onActivated:controller.setting("height",Math.min(600,(controller.prefs.height??360)+24)) }
        KeyboardKey { width:110; height:42; tokens:root.tokens; label:"Motion "+(controller.prefs.reducedMotion?"off":"on"); preview:false; onActivated:controller.setting("reducedMotion",!controller.prefs.reducedMotion) }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Previews "+(controller.prefs.keyPreview===false?"off":"on"); preview:false; onActivated:controller.setting("keyPreview",controller.prefs.keyPreview===false) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Predict "+(controller.prefs.prediction?.enable===false?"off":"on"); preview:false; onActivated:controller.setting("prediction",{enable:controller.prefs.prediction?.enable===false}) }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Squeekboard"; preview:false; onActivated:controller.command(["configure","keyboard.backend",JSON.stringify("squeekboard")]) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Done"; preview:false; onActivated:{ if(controller.settingsOnly) Quickshell.quit(); else controller.settingsOpen=false } }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Sound "+(controller.prefs.sound?.enable?"on":"off"); preview:false; onActivated:controller.setting("sound",{enable:!controller.prefs.sound?.enable}) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Floating"; preview:false; onActivated:controller.setting("floating",{active:!controller.prefs.floating?.active}) }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Typing toolbar"; preview:false; onActivated:controller.setting("toolbar",["emoji","floating","cursor","settings"]) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Editing toolbar"; preview:false; onActivated:controller.setting("toolbar",["clipboard","language",controller.gestureAvailable?"trace":"symbols","settings"]) }
    }
    Flow { width:parent.width; spacing:8
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"HP-OS keyboard"; preview:false; onActivated:controller.command(["configure","keyboard.backend",JSON.stringify("hp-os-qml")]) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"Toggle keyboard"; preview:false; onActivated:controller.command(["toggle"]) }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"English"; preview:false; onActivated:controller.setLanguage("en_US") }
        KeyboardKey { width:150; height:42; tokens:root.tokens; label:"中文 · 拼音"; preview:false; onActivated:controller.setLanguage("zh_CN") }
    }
    KeyboardKey { width:190; height:42; tokens:root.tokens; label:"Gestures "+((controller.policyPrefs["gestures.enable"]??controller.config.gestures?.enable)?"on":"off"); preview:false; onActivated:controller.command(["configure","gestures.enable",JSON.stringify(!(controller.policyPrefs["gestures.enable"]??controller.config.gestures?.enable))]) }
    Flow { width:parent.width; spacing:8
        Repeater { model:["auto","laptop","tablet"]
            KeyboardKey { required property string modelData; width:100; height:42; tokens:root.tokens; label:modelData; preview:false; onActivated:controller.command(["posture",modelData]) }
        }
    }
    Text { width:parent.width; wrapMode:Text.Wrap; color:tokens.secondary; font.pixelSize:12; text:controller.config.keyboard?.mode==="off"?"Keyboard is disabled by Nix policy. Enable it declaratively before selecting an activation mode.":"Activation mode applies independently of touchscreen gestures." }
    Flow { width:parent.width; spacing:8
        Repeater { model:["off","manual","tablet-only","always"]
            KeyboardKey { required property string modelData; width:106; height:42; tokens:root.tokens; label:modelData; preview:false; onActivated:controller.command(["configure","keyboard.mode",JSON.stringify(modelData)]) }
        }
    }
    }
}
