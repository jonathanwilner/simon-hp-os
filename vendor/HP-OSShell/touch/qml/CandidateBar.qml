import QtQuick
Row {
    id:root; required property var controller; required property var tokens
    spacing:8
    Text { width:Math.min(140,root.width*0.22); height:parent.height; verticalAlignment:Text.AlignVCenter; elide:Text.ElideRight; text:controller.preedit; color:tokens.secondary; font.family:tokens.font; font.pixelSize:18 }
    ListView {
        width:Math.max(0,root.width-240); height:parent.height; orientation:ListView.Horizontal; spacing:8; clip:true; model:controller.candidates
        delegate:Rectangle { required property string modelData; required property int index; width:Math.max(52,word.implicitWidth+24); height:40; radius:8; color:tokens.key
            Text { id:word; anchors.centerIn:parent; text:modelData; color:tokens.text; font.family:tokens.font; font.pixelSize:20 }
            TapHandler { onTapped:controller.selectCandidate(index) }
        }
    }
    KeyboardKey { width:40; height:40; tokens:root.tokens; label:"‹"; modifier:true; preview:false; enabledInput:!controller.secure && (controller.inputState.page??0)>0; onActivated:controller.send({op:"page",direction:-1}) }
    KeyboardKey { width:40; height:40; tokens:root.tokens; label:"›"; modifier:true; preview:false; enabledInput:!controller.secure && controller.inputState.hasMore===true; onActivated:controller.send({op:"page",direction:1}) }
}
