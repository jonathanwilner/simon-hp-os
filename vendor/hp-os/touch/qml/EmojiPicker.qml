import QtQuick
import "Layouts.js" as Layouts
GridView {
    id:root; required property var controller; required property var tokens
    cellWidth:Math.max(48,width/Math.floor(width/58)); cellHeight:52; clip:true; model:Layouts.emoji
    delegate:KeyboardKey { required property string modelData; width:root.cellWidth-6; height:46; tokens:root.tokens; label:modelData; preview:false; onActivated:controller.text(modelData) }
}
