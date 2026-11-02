import QtQuick
Column {
    id:root; required property var controller; required property var tokens; spacing:8
    Repeater { model:controller.languages
        KeyboardKey { required property string modelData; width:root.width; height:48; tokens:root.tokens; label:modelData==="zh_CN"?"中文 · 拼音":"English · QWERTY"; modifier:true; preview:false; onActivated:controller.setLanguage(modelData) }
    }
}
