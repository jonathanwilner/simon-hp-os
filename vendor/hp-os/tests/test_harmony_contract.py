"""Integration contract tests. These verify merged source, not a running desktop.

HP_OS_UPSTREAM must point to the pinned pristine iNiR checkout.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get('HP_OS_UPSTREAM', '/tmp/hp-os-upstream'))


class HarmonyContract(unittest.TestCase):
    def test_portable_icon_resolution_and_output_guard(self):
        resolver = (self.runtime / 'services/AppSearch.qml').read_text().split('function resolveIcon(', 1)[1]
        self.assertNotIn('iconPath(iconNameOrPath, fallback)', resolver)
        self.assertIn('Quickshell.hasThemeIcon(iconNameOrPath)', resolver)
        self.assertIn('assets/harmony-application.svg', resolver)
        desktop = (self.runtime / 'modules/background/desktopItems/DesktopItemDelegate.qml').read_text()
        self.assertIn('!root.outputName || root.canvasWidth <= 0', desktop)
        self.assertIn('Number(root.workArea.width ?? 0) < root.width', desktop)
        background = (self.runtime / 'modules/background/Background.qml').read_text()
        self.assertIn('bgRoot.screen?.name && widgetCanvas.width > 0 && widgetCanvas.height > 0', background)
        runner = (ROOT / 'packaging/hp-os').read_text()
        self.assertIn('export QS_ICON_THEME=', runner)

    @classmethod
    def setUpClass(cls):
        if not (UPSTREAM / 'shell.qml').exists():
            raise unittest.SkipTest('HP_OS_UPSTREAM checkout unavailable')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runtime = Path(cls.tmp.name)
        # Apply the shell's declared patches, excluding separate dependency overrides.
        shell_package = (ROOT / 'packaging/package.nix').read_text().split('  qmlDeps =', 1)[0]
        patches = [ROOT / 'patches' / name for name in re.findall(r'\.\./patches/([\w.-]+\.patch)', shell_package)]
        for patch in patches:
            for name in re.findall(r'^--- a/(.+)$', patch.read_text(), re.M):
                dest = cls.runtime / name
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(UPSTREAM / name, dest)
            subprocess.run(['patch', '--batch', '-s', '-p1', '-d', str(cls.runtime), '-i', str(patch)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, name):
        return (self.runtime / name).read_text()

    def test_separate_taskbar_search(self):
        dock = self.read('modules/iris/dock/IrisDock.qml')
        palette = self.read('modules/iris/palette/IrisPalette.qml')
        self.assertIn('HarmonyStartState.toggleSearch()', dock)
        self.assertIn('HarmonyStartState.showAll()', dock)
        self.assertIn('HarmonyStartState.applicationCenter', palette)
        self.assertIn('HarmonyFileSearch.results', palette)
        self.assertIn('root.fileResults', palette)

    def test_family_preserves_single_iris_host(self):
        root = self.read('shell.qml')
        self.assertIn('"harmony": [', root)
        self.assertIn('"modules/harmony/HarmonyPanels.qml"', root)
        self.assertEqual(root.count('source: "ShellIrisPanels.qml"'), 1)
        self.assertIn('Config.isIrisFamily', root)
        self.assertIn('"iris": [', root)
        self.assertIn('"waffle": [', root)

    def test_typed_persistence_schema(self):
        config = self.read('modules/common/Config.qml')
        schema = config.split('property JsonObject harmony: JsonObject {', 1)[1].split('// Panel system', 1)[0]
        for kind, key in [('int','schemaVersion'), ('string','appearance'), ('string','quality'), ('bool','reducedMotion'), ('bool','reducedTransparency'), ('string','locale'), ('string','fontFamily'), ('real','materialIntensity')]:
            self.assertRegex(schema, rf'property {kind} {key}:')
        self.assertIn('["iris", "harmony"].includes', config)

    def test_config_isolation_and_niri_writes(self):
        directories = self.read('modules/common/Directories.qml')
        for key in ['INIR_CONFIG_DIR','INIR_STATE_DIR','INIR_CACHE_DIR']:
            self.assertIn(key, directories)
        self.assertIn('INIR_CONFIG_DIR', self.read('scripts/lib/config-path.sh'))
        for name in ['scripts/niri-config.py', 'services/Autostart.qml', 'services/deferred/NiriKeybinds.qml']:
            self.assertIn('INIR_NIRI_CONFIG_DIR', self.read(name))

    def test_lock_recovery_isolation_preserves_socket_guard(self):
        lock = self.read('modules/lock/Lock.qml')
        self.assertIn('if (Config.options?.panelFamily === "harmony")', lock)
        self.assertIn('Directories.state.replace', lock)
        self.assertIn('"/session-lock.state"', lock)
        self.assertIn('previousSocket === _niriSocket', lock)
        self.assertIn('runtimeDir + "/inir-session-lock.state"', lock)

    def test_control_center_routes_both_hosts_and_persists_actions(self):
        for name, screen in [('modules/iris/control/IrisControlCenter.qml', 'root.screenData'), ('modules/iris/bar/IrisIsland.qml', 'root.targetScreen')]:
            source = self.read(name)
            self.assertIn('import qs.modules.harmony.controlcenter', source)
            self.assertIn('sourceComponent: Config.options?.panelFamily === "harmony" ? harmonyControls : irisControls', source)
            self.assertIn('HarmonyControlCenter {', source)
            self.assertIn('onLoaded: Qt.callLater(focusHarmony)', source)
            self.assertIn('item.focusInitial()', source)
            self.assertIn('IrisQuickPanel {', source)
            self.assertIn('targetScreen: ' + screen, source)
        schema = self.read('modules/common/Config.qml')
        self.assertIn('property JsonObject controlCenter: JsonObject {', schema)
        self.assertIn('property list<string> actions: ["focus", "darkMode", "nightLight", "profiles", "mic", "idle", "snip", "lock", "settings", "session"]', schema)

    def test_harmony_audio_selection_uses_confirmed_node(self):
        devices = self.read('modules/iris/components/IrisDeviceList.qml')
        self.assertIn('Config.options?.panelFamily === "harmony" ? Audio.rawSink?.id : Audio.defaultSink?.id', devices)

    def test_control_frontend_safe_instance_and_keyboard_contract(self):
        source = (ROOT / 'overlay/modules/harmony/controlcenter/HarmonyControlCenter.qml').read_text()
        self.assertIn('GlobalStates.screenLocked = true', source)
        self.assertNotIn('shellPath("scripts/inir")', source)
        for key in ['Keys.onEscapePressed', 'Keys.onPressed', 'Qt.Key_Left', 'Qt.Key_Right', 'Qt.Key_Home', 'Qt.Key_End', 'Accessible.onIncreaseAction', 'Accessible.onDecreaseAction', 'activeFocusOnTab: true']:
            self.assertIn(key, source)
        self.assertNotIn('Keys.onHomePressed', source)
        self.assertNotIn('Keys.onEndPressed', source)
        self.assertIn('Number(Network.wifiEnabled) !== root.requestedWifi', source)
        self.assertIn('Config.setNestedValue("harmony.controlCenter.actions", list)', source)

    def test_slider_key_boundaries_execute_actual_handler(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for extracted JavaScript handler execution')
        source = (ROOT / 'overlay/modules/harmony/controlcenter/HarmonyControlCenter.qml').read_text()
        body = source.split('Keys.onPressed: event => {', 1)[1].split('\n        }', 1)[0]
        script = """
const assert = require('node:assert/strict');
const Qt = {Key_Left:1, Key_Down:2, Key_Right:3, Key_Up:4, Key_Home:5, Key_End:6};
let called = [];
const level = {enabled:true, value:0.98, moved: x => called.push(x)};
const handler = event => { BODY };
function press(key) { const event={key,accepted:false}; handler(event); return event; }
assert.equal(press(Qt.Key_Right).accepted,true); assert.deepEqual(called,[1]);
called=[]; level.value=0.02; press(Qt.Key_Left); assert.deepEqual(called,[0]);
called=[]; press(Qt.Key_Home); press(Qt.Key_End); assert.deepEqual(called,[0,1]);
called=[]; assert.equal(press(999).accepted,false); assert.deepEqual(called,[]);
level.enabled=false; assert.equal(press(Qt.Key_End).accepted,false); assert.deepEqual(called,[]);
""".replace('BODY', body)
        subprocess.run([node, '-e', script], check=True, capture_output=True, text=True)

    def test_hotspot_errors_resolve_portable_notification_binary(self):
        hotspot = self.read('modules/common/models/quickToggles/HotspotToggle.qml')
        self.assertEqual(hotspot.count('Config.options?.panelFamily === "harmony" ? "notify-send" : "/usr/bin/notify-send"'), 2)

    def test_wifi_capability_uses_existing_device_snapshot(self):
        source = self.read('services/Network.qml')
        self.assertIn('root.updateWifiCapability(lines, exitCode);', source)
        self.assertIn('if (Config.options?.panelFamily === "harmony") root.refreshActiveNetworkDetails();', source)
        self.assertIn('"--rescan", "no"', source)
        self.assertIn('if (Config.options?.panelFamily === "harmony" || Quickshell.env("INIR_SAFE_PREVIEW") === "1")', source)
        original = (UPSTREAM / 'services/Network.qml').read_text()
        self.assertEqual(source.count('Process {'), original.count('Process {'))
        for start, end in [('    function enableWifi(', '    function toggleWifi('), ('    function connectToWifiNetwork(', '    function disconnectWifiNetwork(')]:
            self.assertEqual(source.split(start, 1)[1].split(end, 1)[0], original.split(start, 1)[1].split(end, 1)[0])
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for capability parser execution')
        body = source.split('function updateWifiCapability(lines, exitCode): void {', 1)[1].split('\n    }', 1)[0]
        script = """
const assert=require('node:assert/strict'); const root={};
const parse=(lines,exitCode)=>{ BODY };
parse(['ethernet:connected','loopback:connected','full'],0); assert.equal(root.wifiAvailable,false); assert.equal(root.wifiCapabilityKnown,true);
for (const state of ['disconnected','connected','unavailable','connecting (prepare)']) {
 parse(['wifi:'+state,'full'],0); assert.equal(root.wifiAvailable,true);
}
parse(['wifi-p2p:disconnected','ethernet:connected','full'],0); assert.equal(root.wifiAvailable,false);
parse(['wifi:unmanaged','full'],0); assert.equal(root.wifiAvailable,false);
parse(['wifi:connected','full'],10); assert.equal(root.wifiAvailable,false); assert.equal(root.wifiCapabilityKnown,false);
parse(['wifi:connected','full'],0); assert.equal(root.wifiAvailable,true);
parse(['ethernet:connected','full'],0); assert.equal(root.wifiAvailable,false);
""".replace('BODY',body)
        subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)

    def test_slider_custom_fill_keeps_readout_contrast_configurable(self):
        source = self.read('modules/iris/components/IrisCapsuleSlider.qml')
        self.assertIn('property color filledForeground: IrisStyle.surface', source)
        self.assertIn('Readout { ink: root.filledForeground }', source)
        self.assertIn('color: overFill ? root.filledForeground : IrisStyle.text', source)

    def test_control_actions_accept_qml_sequences_and_intentional_empty(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for QML sequence JavaScript execution')
        source = (ROOT / 'overlay/modules/harmony/controlcenter/HarmonyControlCenter.qml').read_text()
        body = source.split('readonly property var actions: {', 1)[1].split('\n    }', 1)[0]
        script = """
const assert=require('node:assert/strict');
const root={defaults:['darkMode','lock']};
const Config={revision:1,options:{harmony:{controlCenter:{actions:null}}}};
const read=()=>{ BODY };
function check(saved,expected) {Config.options.harmony.controlCenter.actions=saved; assert.deepEqual(read(),expected);}
check({0:'darkMode',length:1},['darkMode']);
check({length:0},[]);
check([],[]);
check(['lock','unknown','lock','darkMode'],['lock','darkMode']);
check(null,root.defaults);
""".replace('BODY',body)
        subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)

    def test_pending_connection_actions_ignore_rapid_repeat(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for pending action JavaScript execution')
        source = (ROOT / 'overlay/modules/harmony/controlcenter/HarmonyControlCenter.qml').read_text()
        network_body = source.split('function toggleNetwork() {',1)[1].split('\n    }',1)[0]
        connection_body = source.split('function toggleConnection(model) {',1)[1].split('\n    }',1)[0]
        script = """
const assert=require('node:assert/strict');
let networkCalls=0, hotspotCalls=0, vpnCalls=0, btWrites=0;
const Network={wifiEnabled:false}; const Vpn={busy:false};
const network={mainAction:()=>networkCalls++}, bluetooth={};
const hotspot={toggled:false,mainAction:()=>hotspotCalls++}, vpn={mainAction:()=>vpnCalls++};
const timer=()=>({restart:()=>{},stop:()=>{}});
const wifiTimeout=timer(), bluetoothTimeout=timer(), hotspotTimeout=timer();
const root={requestedWifi:-1,requestedBluetooth:-1,requestedHotspot:-1,bluetoothConfirmed:false,actionError:''};
root.bluetoothAdapter={set enabled(value){btWrites++;}};
root.toggleNetwork=()=>{ NETWORK_BODY };
const toggle=model=>{ CONNECTION_BODY };
toggle(network); toggle(network); assert.equal(networkCalls,1);
toggle(bluetooth); toggle(bluetooth); assert.equal(btWrites,1);
toggle(hotspot); toggle(hotspot); assert.equal(hotspotCalls,1);
Vpn.busy=true; toggle(vpn); assert.equal(vpnCalls,0);
Vpn.busy=false; toggle(vpn); assert.equal(vpnCalls,1);
root.requestedWifi=-1; Network.wifiEnabled=true; toggle(network); assert.equal(root.requestedWifi,0); assert.equal(networkCalls,2);
""".replace('NETWORK_BODY',network_body).replace('CONNECTION_BODY',connection_body)
        subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)

    def test_safe_preview_guards_side_effects(self):
        for name in ['shell.qml', 'services/ThemeService.qml', 'services/FontSyncService.qml', 'services/Idle.qml', 'services/Autostart.qml', 'services/NiriAnimationPresets.qml', 'modules/iris/style/IrisAppsSync.qml']:
            self.assertIn('INIR_SAFE_PREVIEW', self.read(name), name)

    def test_preferences_have_gui_entry(self):
        options = self.read('modules/iris/settings/IrisOptions.qml')
        self.assertIn('label: "HP-OS preferences"', options)
        self.assertIn('"harmony", "settings"', options)
        self.assertIn('value:"harmony"', options)
        self.assertIn('[harmony]="settings gallery close"', self.read('scripts/lib/ipc-registry.sh'))

    def test_harmony_theme_toggle_uses_confirmed_preference(self):
        appearance = self.read('modules/common/Appearance.qml')
        self.assertIn('readonly property bool effectiveDarkMode:', appearance)
        self.assertIn('const newMode = !root.effectiveDarkMode', appearance)
        toggle = self.read('modules/common/models/quickToggles/DarkModeToggle.qml')
        self.assertIn('toggled: Appearance.effectiveDarkMode', toggle)
        self.assertIn('setDarkMode(!Appearance.effectiveDarkMode)', toggle)
        loader = self.read('services/MaterialThemeLoader.qml')
        self.assertIn('Config.setNestedValue("harmony.appearance", dark ? "dark" : "light")', loader)
        self.assertIn('if (Quickshell.env("INIR_SAFE_PREVIEW") === "1")', loader)
        self.assertIn('mode: Appearance.effectiveDarkMode', self.read('services/ThemeService.qml'))

    def test_application_center_excludes_competing_palette(self):
        palette = self.read('modules/iris/palette/IrisPalette.qml')
        self.assertIn('readonly property bool here: !root.harmonyApplicationCenter &&', palette)
        self.assertIn('property bool applicationCenter: true', self.read('modules/common/Config.qml'))

    def test_weather_requires_provider_and_location(self):
        weather = self.read('services/Weather.qml')
        self.assertIn('weatherProvider === "open-meteo" && hasManualCoords', weather)
        self.assertIn('if (root.harmonyFamily || !root.enabled) return;', weather)
        self.assertIn('if (root.harmonyFamily) { root.fetchWeatherFallback(); return; }', weather)
        self.assertIn('property string weatherProvider: "disabled"', self.read('modules/common/Config.qml'))

    def test_control_center_reanchors_on_output_resize(self):
        source = self.read('modules/iris/control/IrisControlCenter.qml')
        self.assertIn('onWidthChanged: if (root.harmonyFamily) root.engaged = false', source)
        self.assertIn('onHeightChanged: if (root.harmonyFamily) root.engaged = false', source)
        self.assertIn('root.positionOrigin.x + root.positionOrigin.width / 2', source)
        body = source.split('function reanchorOrigin(source, oldWidth, oldHeight, newWidth, newHeight) {', 1)[1].split('\n    }', 1)[0]
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for anchor geometry execution')
        script = """
const assert=require('node:assert/strict');
const anchor=(source,oldWidth,oldHeight,newWidth,newHeight)=>{ BODY };
const bottomRight={x:1800,y:1000,width:40,height:40,owner:'stage'};
let a=anchor(bottomRight,1920,1080,2560,1440);
assert.equal(a.x,2440);assert.equal(a.y,1360);assert.equal(a.owner,'stage');
a=anchor(bottomRight,1920,1080,960,540);assert.equal(a.x,840);assert.equal(a.y,460);
a=anchor({x:10,y:20,width:30,height:40},1920,1080,2560,1440);assert.equal(a.x,10);assert.equal(a.y,20);
a=anchor(bottomRight,1920,1080,50,50);assert.equal(a.x,0);assert.equal(a.y,0);
assert.equal(anchor(null,1920,1080,2560,1440),null);
""".replace('BODY',body)
        subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)

    def test_slider_delivered_wheel_respects_scroll_guard(self):
        source = self.read('modules/iris/components/IrisCapsuleSlider.qml')
        body = source.split('onWheel: wheel => {',1)[1].split('\n        }',1)[0]
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable for wheel handler execution')
        script = """
const assert=require('node:assert/strict');
const Config={options:{panelFamily:'harmony'}};
const pointer={wheelAccumulator:0};let values=[];let takeCalls=0;
const root={value:0.9,moved:v=>values.push(v)};
const wheelIntent={scroller:null,moved:false,settled:false,take:e=>{takeCalls++;e.accepted=false;return false}};
const handle=wheel=>{ BODY };
const event=()=>({angleDelta:{x:0,y:-120},pixelDelta:{x:0,y:-15},accepted:true});
handle(event());assert.deepEqual(values,[0.85]);assert.equal(takeCalls,0);
values=[];wheelIntent.scroller={};handle(event());assert.deepEqual(values,[]);assert.equal(takeCalls,1);
wheelIntent.settled=true;handle(event());assert.deepEqual(values,[0.85]);
values=[];Config.options.panelFamily='iris';handle(event());assert.deepEqual(values,[]);assert.equal(takeCalls,2);
""".replace('BODY',body)
        subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)

    def test_picker_rows_expose_accessible_device_identity(self):
        for name, label, state in [
            ('IrisDeviceList.qml', 'Audio.friendlyDeviceName(deviceRow.modelData)', 'deviceRow.current'),
            ('IrisNetworkList.qml', '(networkEntry.modelData.ssid || networkEntry.modelData.bssid || Translation.tr("Wi-Fi"))', 'Boolean(networkEntry.modelData.active)'),
            ('IrisBluetoothList.qml', '(deviceRow.modelData.name || deviceRow.modelData.address || Translation.tr("Bluetooth"))', 'deviceRow.modelData.connected')]:
            source = self.read('modules/iris/components/' + name)
            self.assertIn('Accessible.name: Config.options?.panelFamily === "harmony" ? ' + label, source)
            self.assertIn('Accessible.checked: Config.options?.panelFamily === "harmony" ? ' + state, source)
        bluetooth = self.read('modules/iris/components/IrisBluetoothList.qml')
        self.assertIn('Bluetooth.defaultAdapter?.state === BluetoothAdapterState.Enabled : BluetoothStatus.enabled', bluetooth)
        self.assertIn('model: root.adapterEnabled ? root.devices : []', bluetooth)

    def test_system_dnd_uses_suppression_state_for_harmony(self):
        source = self.read('modules/iris/components/IrisSystemList.qml')
        self.assertIn('Config.options?.panelFamily === "harmony" ? Notifications.silent : focus.toggled', source)
        self.assertIn('detail: root.dndEnabled ?', source)
        self.assertIn('on: root.dndEnabled', source)
        self.assertIn('onToggled: focus.mainAction()', source)
        # Preserve the shared action: only the label's interpretation changes.
        model = (UPSTREAM / 'modules/common/models/quickToggles/NotificationToggle.qml').read_text()
        self.assertIn('Notifications.silent = !Notifications.silent', model)

    def test_night_light_preview_blocks_lazy_service_side_effects(self):
        source = self.read('services/Hyprsunset.qml')
        guard = 'if (Quickshell.env("INIR_SAFE_PREVIEW") === "1") return;'
        for signature in ['_doEnable()', 'enable()', 'disable()', 'fetchState()', 'toggle(active = undefined)']:
            body = source.split('function ' + signature + ' {', 1)[1].lstrip()
            self.assertTrue(body.startswith(guard), signature)
        for compositor in ['CompositorService.isNiri', '!CompositorService.isNiri']:
            self.assertIn('running: Quickshell.env("INIR_SAFE_PREVIEW") !== "1" && ' + compositor, source)
        self.assertTrue(source.split('function onColorTemperatureChanged() {',1)[1].lstrip().startswith(guard))
        self.assertIn('available: !(Config.options?.panelFamily === "harmony" && Quickshell.env("INIR_SAFE_PREVIEW") === "1")', self.read('modules/common/models/quickToggles/NightLightToggle.qml'))
        self.assertIn('available: night.available', self.read('modules/iris/components/IrisDisplayList.qml'))

    def test_private_launch_preserves_compositor_and_bus(self):
        source = self.read('modules/common/functions/ShellExec.qml')
        self.assertIn('["env", "-u", "BASH_ENV", "-u", "ENV", root.bashPath, "--noprofile", "--norc", "-c", script]', source)
        self.assertIn('[...root.shellArgs(script), "inir-open-directory", target]', source)
        script = source.split('const privateScript = `', 1)[1].split('`', 1)[0]
        self.assertNotIn('systemctl', script)
        with tempfile.TemporaryDirectory() as directory:
            hostile = Path(directory) / 'hostile.sh'
            hostile.write_text('export WAYLAND_DISPLAY=wrong DBUS_SESSION_BUS_ADDRESS=wrong\n')
            (Path(directory) / '.bash_profile').write_text(hostile.read_text())
            env = dict(os.environ, HOME=directory, BASH_ENV=str(hostile), ENV=str(hostile),
                       WAYLAND_DISPLAY='private-wayland', DISPLAY=':private', NIRI_SOCKET='/private/niri',
                       DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus', NIXOS_XDG_OPEN_USE_PORTAL='1')
            result = subprocess.run(['env', '-u', 'BASH_ENV', '-u', 'ENV', 'bash', '--noprofile', '--norc',
                                     '-c', script, 'harmony-launch', directory, 'env'], env=env,
                                    check=True, capture_output=True, text=True)
            actual = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
            for key in ['WAYLAND_DISPLAY', 'DISPLAY', 'NIRI_SOCKET', 'DBUS_SESSION_BUS_ADDRESS']:
                self.assertEqual(actual[key], env[key])
            self.assertEqual(actual['PWD'], directory)
            self.assertNotIn('BASH_ENV', actual)
            self.assertNotIn('NIXOS_XDG_OPEN_USE_PORTAL', actual)

    def test_plain_desktop_click_does_not_snap_position(self):
        source = self.read('modules/background/desktopItems/DesktopItemDelegate.qml')
        release = source.split('onReleased: event => {', 1)[1].split('onCanceled:', 1)[0]
        self.assertLess(release.index('Math.abs(root.x - root._pressX) <= 1'),
                        release.index('const pos = root._clampPosition'))
        self.assertIn('root._positionOverride = false\n                return', release)

    def test_pc_application_center_layout_and_launch(self):
        source = (ROOT / 'overlay/modules/harmony/launcher/HarmonyApplicationCenter.qml').read_text()
        self.assertIn('anchors { top: true; left: true; right: true; bottom: true }', source)
        self.assertIn('margins.bottom:', source)
        self.assertIn('blurEnabled: true', source)
        self.assertIn('Math.min(8,', source)
        self.assertIn('width: 90; height: 90', source)
        self.assertIn('appIcon.status === Image.Error || appIcon.status === Image.Null', source)
        self.assertNotIn('root.categories', source)
        self.assertNotIn('Advanced search', source)
        launch = source.split('function openEntry(entry, newWindow) {', 1)[1].split('    Image {', 1)[0]
        self.assertIn('AppSearch.lookupDesktopEntry(win.app_id)', launch)
        self.assertIn('if (existing && !newWindow) NiriService.focusWindow(existing.id)', launch)
        self.assertIn('else if (!AppSearch.launchEntry(entry)) return', launch)
        self.assertIn('GlobalStates.searchOpen = false', launch)
        self.assertIn('Keys.onEscapePressed: root.goBack()', source)
        self.assertIn('TaskbarApps.togglePin(root.menuEntry.id)', source)

    def test_start_panel_has_separate_action_and_safe_input_layers(self):
        dock = self.read('modules/iris/dock/IrisDock.qml')
        self.assertIn('HarmonyStartState.toggle()', dock)
        menu = (ROOT / 'overlay/modules/harmony/launcher/HarmonyStartMenu.qml').read_text()
        dismiss, surface = menu.split('id: surface', 1)
        self.assertIn('WlrLayershell.layer: WlrLayer.Top', dismiss)
        self.assertIn('WlrLayershell.layer: WlrLayer.Overlay', surface)
        self.assertIn('margins.bottom:', dismiss)
        self.assertIn('onAccepted: { HarmonyStartState.logOut() }', menu)
        state = (ROOT / 'overlay/modules/harmony/launcher/HarmonyStartState.qml').read_text()
        self.assertIn('id: accountSettingsProbe', state)
        self.assertNotIn('Process {', menu)
        self.assertEqual(menu.count('visible: HarmonyStartState.opened'), 2)
        panels = (ROOT / 'overlay/modules/harmony/HarmonyPanels.qml').read_text()
        self.assertNotIn('active: HarmonyStartState.opened', panels)
        self.assertIn('NiriService.focusWindow(existing.id)', state)
        self.assertIn('ShellExec.execDetachedArgs(["xdg-open", url])', state)

    def test_existing_backends_are_preserved(self):
        # Notification ownership and live controls must stay upstream-owned.
        for name in ['services/Notifications.qml','services/Audio.qml','services/BluetoothStatus.qml','services/DesktopItems.qml','services/NiriService.qml']:
            original = (UPSTREAM / name).read_text()
            expected = original
            for expr in ['(Config.options?.panelFamily ?? "ii")', 'Config.options?.panelFamily']:
                expected = expected.replace(expr + ' === "iris"', 'Config.isIrisFamily')
                expected = expected.replace(expr + ' !== "iris"', '!Config.isIrisFamily')
            if name == 'services/DesktopItems.qml':
                # Only the Harmony cell dimensions change; persistence, dragging,
                # collision detection and all other families stay upstream-owned.
                expected = expected.replace('itemWidth: 92', 'itemWidth: Config.options?.panelFamily === "harmony" ? 104 : 92')
                expected = expected.replace('itemHeight: 94', 'itemHeight: Config.options?.panelFamily === "harmony" ? 104 : 94')
            merged = self.read(name) if (self.runtime / name).exists() else original
            self.assertEqual(merged, expected, name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
