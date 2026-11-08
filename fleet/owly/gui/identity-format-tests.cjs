const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, 'IdentityFormat.js'), 'utf8').replace(/^\.pragma library\s*/, ''), context);
for (const [url, expected] of [
    ['file:///home/me/My%20Identity', '/home/me/My Identity'],
    ['file:///home/me/%E8%BA%AB%E4%BB%BD', '/home/me/身份'],
    ['file:///tmp/100%25%20ready', '/tmp/100% ready'],
    ['file:///tmp/%2520', '/tmp/%20'],
    ['file:///tmp/%00', ''],
    ['file:///tmp/%ZZ', ''],
    ['file://remote/share', ''],
    ['https://example.org/identity', ''],
    ['/tmp/identity', ''],
]) assert.equal(context.localPath(url), expected, url);
console.log('Identity folder URL checks passed (9 cases).');
