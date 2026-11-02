.pragma library
function character(label, alternate, options) { return Object.assign({label:label, text:label, alternate:alternate || "", weight:1}, options || {}) }
function action(label, action, weight) { return {label:label, action:action, weight:weight || 1.5} }
const accents = {a:"àáâäæãåā",e:"èéêëē",i:"ìíîïī",o:"òóôöœøōõ",u:"ùúûüū",c:"çćč",n:"ñń",s:"ßśš",y:"ýÿ",z:"žźż"}
function letters(upper) {
 const rows=["qwertyuiop","asdfghjkl","zxcvbnm"]
 return rows.map((row, r) => {
  const keys=row.split("").map((c,i) => character(upper ? c.toUpperCase():c, r===0 ? "1234567890"[i] : "", {base:c, accents:accents[c] || ""}))
  if (r===2) { keys.unshift(action("⇧","shift")); keys.push(action("⌫","backspace")) }
  return keys
 })
}
function symbols(second) {
 const rows=second ? [["[","]","{","}","#","%","^","*","+","="],["_","\\","|","~","<",">","€","£","¥"],["•","…","¿","¡","§","°","©"]] : [["1","2","3","4","5","6","7","8","9","0"],["@","#","$","_","&","-","+","(",")"],["!","\"","'",":",";","/","?"]]
 return rows.map((row,r) => { const keys=row.map(c => character(c)); if(r===2){keys.unshift(action(second ? "123":"=\\<","more"));keys.push(action("⌫","backspace"))}return keys })
}
function numeric(phone) {
 return [["1","2","3"],["4","5","6"],["7","8","9"],[phone ? "+" : ".","0",phone ? "#" : "-"]].map(row=>row.map(c=>character(c)))
}
const emoji = ["😀","😃","😄","😁","😆","😅","😂","🙂","🙃","😉","😊","😍","🥰","😘","😎","🤔","😴","😢","😭","😡","🤗","🤩","🥳","👍","👎","👏","🙌","🙏","💪","👋","❤️","🧡","💛","💚","💙","💜","✨","⭐","🔥","🎉","✅","❌","💯","🌈","☀️","🌙","🌻","🍀","🐱","🐶","🐼","🦊","🍎","🍊","🍕","☕","⚽","🏀","🎵","🚀","✈️","🏠","💡","📚"]
