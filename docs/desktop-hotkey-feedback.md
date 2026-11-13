# Desktop hotkey feedback

HP-OS displays volume, speaker mute, microphone mute, brightness, keyboard state,
and explicit media actions in an independent floating overlay. The toolbar keeps
passive device, battery, recording, and track notifications. Toolbar timers do
not consume or clear the floating overlay's requests.

The overlay is horizontally centered. Its bottom clearance is the greater of
12% of the display height and the dock/frame clearance plus 18 scaled pixels.
This keeps feedback above the dock, including on shorter displays. Existing
level appearance, duration, fullscreen, and module-enable preferences remain
in effect. HP-OS uses lower-center placement regardless of the old top-position
preference.

The placement follows the OpenHarmony PC reference implementation, which uses
`x = (screenWidth - panelWidth) / 2` and
`y = screenHeight * 0.88 - panelHeight`. OpenHarmony's reference dimensions are
312 × 32 vp and its timeout is 2 seconds. HP-OS retains its own existing capsule
size and configurable duration. This is a source reference, not verification of
proprietary HarmonyOS PC behavior.

References at OpenHarmony commit `9e9e76004db68613f5e1201d2aeee63b9de7a384`:

- [Shared constants](https://github.com/openharmony/window_scene_board/blob/9e9e76004db68613f5e1201d2aeee63b9de7a384/staticcommon/systemuicommon/src/main/ets/plugin/LocalWindowManager.ts#L119-L128)
- [Volume placement](https://github.com/openharmony/window_scene_board/blob/9e9e76004db68613f5e1201d2aeee63b9de7a384/feature/volume/volumepanelcomponent/src/main/ets/com/ohos/common/VolumeWindowController.ets#L459-L474)
- [Brightness placement](https://github.com/openharmony/window_scene_board/blob/9e9e76004db68613f5e1201d2aeee63b9de7a384/product/pcbase/src/main/ets/SceneBoard/brightnesspanel/pages/SCBBrightnessPanel.ets#L173-L181)

Implementation: `vendor/HP-OSShell/patches/hpos-centered-osd.patch`, applied after
`hpos-media-key-osd.patch`. The `hpos` family shares Iris panels; it does not have
a separate hotkey overlay implementation.

Regression check: the `test_hotkeys_use_independent_centered_osd` contract test
applies all declared patches to the pinned upstream source. It checks the loader,
request ownership, preserved passive events, centering, dock clearance, and
non-interactive overlay. Live desktop acceptance must additionally trigger the
actual hotkeys and inspect the resulting overlay.
