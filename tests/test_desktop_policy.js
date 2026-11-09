// Exercise the evaluated policy as polkit does, including prohibited scopes.
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');
for (const file of process.argv.slice(2)) {
  let rule;
  vm.runInNewContext(JSON.parse(fs.readFileSync(file)).polkit, {
    polkit: { addRule: fn => { rule = fn; }, Result: { YES: 'yes' } }
  });
  const subject = wheel => ({ isInGroup: group => wheel && group === 'wheel' });
  for (const action of ['org.freedesktop.color-manager.create-profile',
      'org.opensuse.cupspkhelper.mechanism.all-edit',
      'org.freedesktop.Flatpak.app-install',
      'org.freedesktop.packagekit.system-sources-refresh',
      'org.freedesktop.NetworkManager.enable-disable-statistics']) {
    assert.equal(rule({ id: action }, subject(true)), 'yes');
    assert.equal(rule({ id: action }, subject(false)), undefined);
  }
  for (const action of ['org.libvirt.unix.manage', 'org.freedesktop.systemd1.manage-units',
      'org.freedesktop.NetworkManager.settings.modify.system', 'org.freedesktop.FlatpakOther']) {
    assert.equal(rule({ id: action }, subject(true)), undefined);
  }
  console.log(`${file}: desktop policy scope passed`);
}
