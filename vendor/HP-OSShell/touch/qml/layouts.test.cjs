// Model checks complement actual Wayland rendering and native input tests.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/Layouts.js','utf8').replace('.pragma library','');
const context=vm.createContext({});vm.runInContext(source,context);
const letters=context.letters(false).flat();
assert.equal(letters.filter(k=>k.base).map(k=>k.base).sort().join(''),'abcdefghijklmnopqrstuvwxyz');
assert.equal(context.letters(true).flat().find(k=>k.base==='a').label,'A');
assert.equal(context.letters(false)[0].map(k=>k.alternate).join(''),'1234567890');
for(const layout of [context.letters(false),context.symbols(false),context.symbols(true),context.numeric(false),context.numeric(true)]) {
 assert(layout.every(row=>row.length>0 && row.every(key=>key.weight>0 && key.label.length>0)));
}
assert(context.symbols(false).flat().some(k=>k.action==='more'));
assert(context.symbols(true).flat().some(k=>k.label==='€'));
assert(context.numeric(true).flat().some(k=>k.label==='+'));
console.log('Keyboard layout checks passed');
