const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(`${__dirname}/web/app.js`, 'utf8').split('els.refreshButton.addEventListener')[0];
const context = vm.createContext({document: {getElementById() { return {}; }, querySelector() { return {}; }}});
vm.runInContext(source, context);
assert.equal(vm.runInContext('progressLabel(null)', context), '');
assert.match(vm.runInContext('progressLabel({percent:99.999, completed:999, total:1000, scope:"phase", label:"Download", unit:"bytes"})', context), /Download \(phase\): 99\.9%/);
assert.match(vm.runInContext('progressHtml({percent:42, completed:42, total:100, label:"<script>"})', context), /&lt;script&gt;/);
assert.equal(vm.runInContext('manifestViewKey({machines:[{sessions:[{progress:{percent:1}}]}]}) === manifestViewKey({machines:[{sessions:[{progress:{percent:2}}]}]})', context), false);
console.log('Progress UI checks passed');

(async () => {
  function element() {
    return {children: [], textContent: '', classList: {add() {}, toggle() {}},
      replaceChildren() {this.children = [];}, append(child) {this.children.push(child);}, addEventListener() {}};
  }
  const elements = {};
  const requests = [];
  const fixture = {machines: [{host: 'goran', total_sessions: 100, sessions: [{host:'goran', safe_session:'download',
    session:'download', status:'running', updated_at:'2026-10-04T23:00:00Z', log_url:'machines/goran/logs/download.txt',
    progress:{percent:25.5, completed:34e9, total:135e9, scope:'phase', label:'Model download', unit:'bytes'}}]}], totals:{running:1}};
  const browser = vm.createContext({
    document: {getElementById(id) {return elements[id] ||= element();}, querySelector() {return element();}, createElement() {return element();}},
    async fetch(url) {requests.push(url); return {ok:true, async json() {return fixture;}, async text() {return 'download active';}}},
  });
  vm.runInContext(source, browser);
  await vm.runInContext('refresh()', browser);
  assert.match(requests[0], /^\/dashboard\/manifest\.json\?/);
  assert.equal(elements.runningCount.textContent, 1);
  assert.equal(elements.machines.children.length, 1);
  assert.match(elements.selectedMeta.textContent, /Model download \(phase\): 25\.5%/);
  assert.equal(elements.logOutput.textContent, 'download active');
  console.log('Dashboard initialization and log selection passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
