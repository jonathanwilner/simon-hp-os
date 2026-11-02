import QtQuick
import qs.modules.harmony.design
Text {
    property string role: "body"
    color: role === "secondary" ? HarmonyTokens.secondary : HarmonyTokens.text
    font.family: HarmonyTokens.fontFamily
    font.pixelSize: role === "display" ? HarmonyTokens.display : role === "title" ? HarmonyTokens.title : role === "secondary" ? HarmonyTokens.caption : HarmonyTokens.body
    font.weight: role === "title" || role === "display" ? 600 : 400
    font.variableAxes: ({ "wght": role === "title" || role === "display" ? 600 : 400 })
    lineHeight: 1.3
    wrapMode: Text.WordWrap
}
