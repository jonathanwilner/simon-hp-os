import QtQuick
import qs.modules.hpos.design
Text {
    property string role: "body"
    color: role === "secondary" ? HposTokens.secondary : HposTokens.text
    font.family: HposTokens.fontFamily
    font.pixelSize: role === "display" ? HposTokens.display : role === "title" ? HposTokens.title : role === "secondary" ? HposTokens.caption : HposTokens.body
    font.weight: role === "title" || role === "display" ? 600 : 400
    font.variableAxes: ({ "wght": role === "title" || role === "display" ? 600 : 400 })
    lineHeight: 1.3
    wrapMode: Text.WordWrap
}
