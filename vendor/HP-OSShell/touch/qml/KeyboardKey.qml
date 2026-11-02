import QtQuick
Item {
    id: root
    required property var tokens
    property string label: ""
    property string alternate: ""
    property string accents: ""
    property bool modifier: false
    property bool accent: false
    property bool repeatable: false
    property bool preview: true
    property bool enabledInput: true
    property bool space: false
    property bool cursorSwipe: false
    property bool wordDelete: false
    property bool held: false
    property bool consumed: false
    property real originX: 0
    property real originY: 0
    property real lastCursorX: 0
    property int selection: 0
    signal activated(string value)
    signal cursor(int direction)
    signal options()
    signal deleteWord()
    function begin(x,y) { if (!enabledInput) return; held=true; consumed=false; originX=x; originY=y; lastCursorX=x; selection=0; hold.restart() }
    function move(x,y) {
        if (!held) return
        if (alternates.visible) { selection=Math.max(0,Math.min(accents.length-1, Math.floor(x / Math.max(1,width) * accents.length))); return }
        if (wordDelete && x-originX < -40) { if(!consumed) deleteWord(); consumed=true; hold.stop(); repeatTimer.stop(); return }
        if ((space || cursorSwipe) && Math.abs(x-lastCursorX)>(space?18:36) && Math.abs(y-originY)<24) { consumed=true; cursor(x>lastCursorX?1:-1); lastCursorX=x; hold.stop() }
        if (!space && y-originY < -30 && alternate.length) { consumed=true; hold.stop() }
    }
    function end(x,y) {
        if (!held) return
        if (alternates.visible) activated(accents.charAt(selection))
        else if (!consumed) activated(label)
        else if (!space && y-originY < -30 && alternate.length) activated(alternate)
        held=false; hold.stop(); repeatTimer.stop(); alternates.visible=false
    }
    Rectangle { anchors.fill: keycap; anchors.topMargin:2; anchors.bottomMargin:-2; radius:tokens.radius; color:tokens.shadow }
    Rectangle {
        id:keycap; anchors.fill:parent; anchors.margins:1; radius:tokens.radius
        color:root.held?tokens.pressed:root.accent?tokens.accent:root.modifier?tokens.modifier:tokens.key
        scale:root.held?0.96:1
        Behavior on scale { NumberAnimation { duration:tokens.feedbackDuration } }
        Behavior on color { ColorAnimation { duration:tokens.feedbackDuration } }
        Text { anchors.centerIn:parent; text:root.label; color:root.accent?tokens.onAccent:tokens.text; font.family:tokens.font; font.pixelSize:Math.min(23*tokens.scale,parent.height*0.4); font.weight:Font.Medium }
        Text { anchors.right:parent.right; anchors.top:parent.top; anchors.margins:5; text:root.alternate; color:tokens.secondary; font.pixelSize:10*tokens.scale }
    }
    Rectangle { visible:root.held && root.preview && !root.modifier && !root.space && !alternates.visible; z:30; width:Math.max(root.width,48); height:52; anchors.bottom:parent.top; anchors.horizontalCenter:parent.horizontalCenter; radius:tokens.radius; color:tokens.key; border.color:tokens.shadow
        Text { anchors.centerIn:parent; text:root.label; color:tokens.text; font.pixelSize:28; font.family:tokens.font }
    }
    Rectangle {
        id:alternates; visible:false; z:40; anchors.bottom:parent.top; width:root.width; height:48; radius:tokens.radius; color:tokens.key; border.color:tokens.accent
        Text { anchors.centerIn:parent; text:root.accents.charAt(root.selection); color:tokens.text; font.pixelSize:26 }
    }
    MultiPointTouchArea {
        anchors.fill:parent; minimumTouchPoints:1; maximumTouchPoints:1; mouseEnabled:true
        onPressed: points => root.begin(points[0].x,points[0].y)
        onUpdated: points => root.move(points[0].x,points[0].y)
        onReleased: points => root.end(points[0].x,points[0].y)
        onCanceled: { root.held=false; hold.stop(); repeatTimer.stop(); alternates.visible=false }
    }
    Timer { id:hold; interval:420; onTriggered: {
        if (root.repeatable) { root.consumed=true; root.activated(root.label); repeatTimer.start() }
        else if (root.accents.length) alternates.visible=true
        else if (root.space || root.modifier) { root.consumed=true; root.options() }
    } }
    Timer { id:repeatTimer; interval:65; repeat:true; onTriggered:root.activated(root.label) }
}
