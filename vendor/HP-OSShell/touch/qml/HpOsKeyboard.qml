import QtQuick
import Quickshell
import Quickshell.Wayland
import "Layouts.js" as Layouts
PanelWindow {
    id:root
    required property var controller
    property bool floating:(controller.config.keyboard?.floating?.enable??true) && (controller.prefs.floating?.active??false)
    property string positionKey:(screen?.name??"default")+((screen?.width??1)>(screen?.height??1)?":landscape":":portrait")
    property real floatingX:controller.prefs.floatPositions?.[positionKey]?.x??0.5
    property real floatingY:controller.prefs.floatPositions?.[positionKey]?.y??0.05
    readonly property real availableX:Math.max(0,(screen?.width??1280)-implicitWidth)
    readonly property real availableY:Math.max(0,(screen?.height??800)-implicitHeight)
    visible:(controller.shown || surface.opacity>0) && !controller.settingsOnly
    screen:Quickshell.screens.find(s=>s.name===controller.runtime.screen) || Quickshell.screens[0]
    onPositionKeyChanged:{floatingX=controller.prefs.floatPositions?.[positionKey]?.x??0.5; floatingY=controller.prefs.floatPositions?.[positionKey]?.y??0.05}
    color:"transparent"
    anchors { bottom:true; left:true; right:!root.floating }
    margins.left:floating?Math.round(floatingX*availableX):0
    margins.bottom:floating?Math.round(floatingY*availableY):0
    implicitWidth:floating?Math.min(720,(screen?.width??1280)-24):(screen?.width??1280)
    implicitHeight:Math.min((screen?.height??800)*0.65,Math.max(controller.numeric && controller.layout==="letters"?380:330,controller.prefs.height??360))
    exclusiveZone:floating || !controller.shown?0:implicitHeight
    WlrLayershell.namespace:"hp-os-keyboard"
    WlrLayershell.layer:WlrLayer.Overlay
    WlrLayershell.keyboardFocus:WlrKeyboardFocus.None
    KeyboardTokens {
        id:theme
        dark:controller.prefs.colorScheme==="dark" || (controller.prefs.colorScheme!=="light" && controller.systemDark)
        reducedMotion:controller.shellReducedMotion || (controller.prefs.reducedMotion??false)
        scale:Math.max(0.8,Math.min(1.4,controller.prefs.keyScale??1))
        accent:controller.prefs.accentColor || (dark?"#83baff":"#0a59f7")
    }
    function action(name) {
        if(name==="shift") controller.shiftPressed()
        else if(name==="backspace") controller.key("BackSpace")
        else if(name==="enter") controller.key("Return")
        else if(name==="space") controller.text(" ")
        else if(name==="language") controller.cycleLanguage()
        else if(name==="symbols") controller.layout="symbols"
        else if(name==="letters") controller.layout="letters"
        else if(name==="more") controller.layout=controller.layout==="more"?"symbols":"more"
        else if(name==="emoji") controller.layout="emoji"
        else if(name==="left") controller.key("Left")
        else if(name==="right") controller.key("Right")
        else if(name==="tab") controller.key("Tab")
        else if(name==="home") controller.key("Home")
        else if(name==="end") controller.key("End")
        else if(name==="selectall") controller.key("a",["Control"])
        else if(name==="paste") controller.paste()
    }
    Rectangle {
        id:surface; anchors.fill:parent; color:theme.canvas; radius:root.floating?18:0
        opacity:controller.shown?1:0
        Behavior on opacity { NumberAnimation { duration:theme.revealDuration } }
        transform:Translate { y:controller.shown?0:20; Behavior on y { NumberAnimation { duration:theme.revealDuration; easing.type:Easing.OutCubic } } }
        Column {
            id:content; anchors.fill:parent; anchors.margins:theme.inset; spacing:theme.gap
            Item { width:parent.width; height:root.floating?16:2
                Rectangle { visible:root.floating; anchors.centerIn:parent; width:64; height:5; radius:3; color:theme.secondary }
                DragHandler {
                    enabled:root.floating; target:null
                    property real startX:0; property real startY:0
                    onActiveChanged: {
                        if(active) { startX=root.floatingX; startY=root.floatingY }
                        else { const positions=Object.assign({},controller.prefs.floatPositions??{}); positions[root.positionKey]={x:root.floatingX,y:root.floatingY}; controller.setting("floatPositions",positions) }
                    }
                    onTranslationChanged: { root.floatingX=Math.max(0,Math.min(1,startX+translation.x/Math.max(1,root.availableX))); root.floatingY=Math.max(0,Math.min(1,startY-translation.y/Math.max(1,root.availableY))) }
                }
            }
            KeyboardToolbar { width:parent.width; height:40; controller:root.controller; tokens:theme }
            Item {
                width:parent.width; height:parent.height-y
                KeyboardSettings { anchors.fill:parent; visible:controller.settingsOpen; controller:root.controller; tokens:theme }
                LanguageSwitcher { anchors.fill:parent; visible:controller.languagesOpen && !controller.settingsOpen; controller:root.controller; tokens:theme }
                Column {
                    anchors.fill:parent; spacing:theme.gap; visible:!controller.settingsOpen && !controller.languagesOpen
                    Item {
                        width:parent.width; height:40
                        CandidateBar { anchors.fill:parent; visible:controller.candidates.length>0; controller:root.controller; tokens:theme }
                        Text { anchors.centerIn:parent; visible:controller.candidates.length===0; text:!controller.available?"Input backend unavailable":!controller.active?"Select a compatible text field":controller.secure?"Secure input":controller.language==="zh_CN"?"拼音 · Pinyin":controller.caps?"Caps Lock":"English"; color:theme.secondary; font.family:theme.font; font.pixelSize:14 }
                    }
                    Item {
                        width:parent.width; height:parent.height-y
                        EmojiPicker { anchors.fill:parent; anchors.bottomMargin:48+theme.gap; visible:controller.layout==="emoji"; controller:root.controller; tokens:theme }
                        Column {
                            id:rows; anchors.fill:parent; spacing:theme.gap; visible:controller.layout!=="emoji"
                            property var keys:controller.cursorMode?[[Layouts.action("←","left"),Layouts.action("→","right"),Layouts.action("⌫","backspace")],[Layouts.action("Home","home"),Layouts.action("End","end"),Layouts.action("Tab","tab")],[Layouts.action("Select all","selectall"),Layouts.action("Paste","paste")]]:controller.numeric && controller.layout==="letters"?Layouts.numeric(controller.phone):controller.layout==="symbols"||controller.layout==="more"?Layouts.symbols(controller.layout==="more"):Layouts.letters(controller.shift||controller.caps)
                            Repeater { model:rows.keys
                                KeyboardRow { required property var modelData; width:rows.width; height:(rows.height-theme.gap*rows.keys.length)/(rows.keys.length+1); keys:modelData; controller:root.controller; tokens:theme; onAction:name=>root.action(name) }
                            }
                            KeyboardRow { width:parent.width; height:(rows.height-theme.gap*rows.keys.length)/(rows.keys.length+1); controller:root.controller; tokens:theme; keys:root.bottomRow(); onAction:name=>root.action(name) }
                        }
                        GestureTrace {
                            anchors.fill:parent; anchors.bottomMargin:48+theme.gap
                            visible:controller.traceMode && controller.gestureAvailable && controller.layout==="letters"
                            controller:root.controller; tokens:theme
                        }
                        KeyboardRow { anchors.left:parent.left; anchors.right:parent.right; anchors.bottom:parent.bottom; height:48; visible:controller.layout==="emoji"; controller:root.controller; tokens:theme; keys:root.bottomRow(); onAction:name=>root.action(name) }
                    }
                }
            }
        }
    }
    function bottomRow() {
        return [Layouts.action(controller.layout==="letters"?"123":"ABC",controller.layout==="letters"?"symbols":"letters",1.4),Layouts.action(controller.language==="zh_CN"?"中 / En":"En / 中","language",1.5),Layouts.action("☺","emoji",1),Layouts.action(controller.language==="zh_CN"?"空格":"space","space",4),controller.numeric?Layouts.action("⌫","backspace"):Layouts.character("."),Layouts.action(controller.returnLabel,"enter",1.8)]
    }
}
