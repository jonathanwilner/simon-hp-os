import QtQuick
Item {
    id:root
    required property var controller
    required property var tokens
    property var points:[]
    property var letters:[]
    property double started:0
    function keyAt(x,y) {
        const rows=["qwertyuiop","asdfghjkl","zxcvbnm"]
        const row=Math.max(0,Math.min(2,Math.floor(y/height*3)))
        const inset=row===2?width*0.15:0
        if(x<inset || x>width-inset) return ""
        return rows[row][Math.max(0,Math.min(rows[row].length-1,Math.floor((x-inset)/(width-2*inset)*rows[row].length)))]
    }
    function append(x,y) {
        if(points.length>=2048) return
        points.push({x:x/width,y:y/height,t:Date.now()-started})
        const key=keyAt(x,y)
        if(key && letters[letters.length-1]!==key) letters.push(key)
        trail.requestPaint()
    }
    Canvas {
        id:trail; anchors.fill:parent
        onPaint: {
            const ctx=getContext("2d");ctx.clearRect(0,0,width,height)
            if(!root.points.length) return
            ctx.strokeStyle=root.tokens.accent;ctx.lineWidth=5;ctx.lineCap="round";ctx.lineJoin="round";ctx.beginPath()
            ctx.moveTo(root.points[0].x*width,root.points[0].y*height)
            for(let i=1;i<root.points.length;i++)ctx.lineTo(root.points[i].x*width,root.points[i].y*height)
            ctx.stroke()
        }
    }
    MultiPointTouchArea {
        anchors.fill:parent; maximumTouchPoints:1; mouseEnabled:true
        onPressed: p=>{ clear.stop(); root.points=[];root.letters=[];root.started=Date.now();root.append(p[0].x,p[0].y) }
        onUpdated: p=>root.append(p[0].x,p[0].y)
        onReleased: {
            if(root.letters.length===1) root.controller.letter(root.letters[0])
            else if(root.letters.length>1)root.controller.send({op:"gesture",keys:root.letters,points:root.points})
            clear.start()
        }
        onCanceled:{root.points=[];root.letters=[];trail.requestPaint()}
    }
    Timer { id:clear; interval:tokens.reducedMotion?1:180; onTriggered:{root.points=[];root.letters=[];trail.requestPaint()} }
    onVisibleChanged:if(!visible){points=[];letters=[];trail.requestPaint()}
}
