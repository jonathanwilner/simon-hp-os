const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

let rule;
vm.runInNewContext(fs.readFileSync(process.env.RADIO_POLICY_SOURCE ||
  path.join(__dirname, 'radio-policy.rules'), 'utf8'), {
  polkit: { addRule: (callback) => { rule = callback; }, Result: { YES: 'yes' } },
});

function authorize(action, member, active = false, local = false) {
  return rule({ id: action }, {
    user: 'desktop-user', active, local,
    isInGroup: (group) => member && group === 'omdrop',
  });
}

test('explicit radio group can use desktop, background and SSH sessions', () => {
  for (const action of ['org.omarchy.omdrop.radio', 'io.github.t4t5.Owly.acquire']) {
    for (const active of [false, true]) {
      for (const local of [false, true]) {
        assert.equal(authorize(action, true, active, local), 'yes');
      }
    }
  }
});

test('nonmembers retain the distribution policy', () => {
  for (const action of ['org.omarchy.omdrop.radio', 'io.github.t4t5.Owly.acquire']) {
    assert.equal(authorize(action, false), undefined);
    assert.equal(authorize(action, false, true, true), undefined);
  }
});

test('membership never grants generic admin actions or prefix matches', () => {
  for (const action of [
    'org.freedesktop.policykit.exec',
    'org.freedesktop.systemd1.manage-units',
    'org.freedesktop.NetworkManager.settings.modify.system',
    'org.omarchy.omdrop.radio.other',
    'io.github.t4t5.Owly.acquire.other',
    '',
  ]) {
    assert.equal(authorize(action, true, true, true), undefined);
  }
});
