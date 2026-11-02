package brightness

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

func testPanel(t *testing.T) *goranPanelBackend {
	t.Helper()
	dir := t.TempDir()
	state := filepath.Join(dir, "percent")
	helper := filepath.Join(dir, "helper")
	sh, err := exec.LookPath("sh")
	if err != nil {
		t.Fatal(err)
	}
	script := "#!" + sh + "\nset -eu\nif [ \"$1\" = set ]; then printf '%s\\n' \"$2\" > \"$PANEL_TEST_STATE\"; fi\n"
	if err := os.WriteFile(helper, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PANEL_TEST_STATE", state)
	return &goranPanelBackend{helper, state}
}

func TestGoranPanelSetAndLimits(t *testing.T) {
	b := testPanel(t)
	for _, tc := range []struct {
		input       int
		exponential bool
		want        int
	}{
		{65, false, 65}, {0, false, 5}, {100, false, 100}, {50, true, 25},
	} {
		if err := b.SetBrightnessWithExponent(goranPanelID, tc.input, tc.exponential, 2); err != nil {
			t.Fatal(err)
		}
		devices := b.appendDevice(nil)
		if len(devices) != 1 || devices[0].CurrentPercent != tc.want {
			t.Fatalf("got %+v, want %d", devices, tc.want)
		}
	}
	if err := b.SetBrightnessWithExponent("other", 50, false, 1); err == nil {
		t.Fatal("accepted unknown panel")
	}
	if err := b.SetBrightnessWithExponent(goranPanelID, 101, false, 1); err == nil {
		t.Fatal("accepted invalid percentage")
	}
}

func TestGoranPanelNativePreferenceAndInvalidState(t *testing.T) {
	b := testPanel(t)
	brokenNative := []Device{{ID: "backlight:nvidia_0", Class: ClassBacklight}}
	if got := b.appendDevice(brokenNative); len(got) != 1 || got[0].ID != goranPanelID {
		t.Fatalf("NVIDIA OLED device displaced the AUX helper: %+v", got)
	}
	native := []Device{{ID: "native", Class: ClassBacklight}}
	if got := b.appendDevice(native); len(got) != 1 || got[0].ID != "native" {
		t.Fatalf("got %+v", got)
	}
	if err := os.WriteFile(b.stateFile, []byte("broken"), 0600); err != nil {
		t.Fatal(err)
	}
	if got := b.appendDevice(nil); len(got) != 0 {
		t.Fatalf("advertised invalid state: %+v", got)
	}
}

func TestGoranPanelManagerAndKeyboardSync(t *testing.T) {
	b := testPanel(t)
	m := &Manager{goranBackend: b, stopChan: make(chan struct{}), logindReady: true, logindBackend: &LogindBackend{}}
	m.updateState()
	if err := m.SetBrightness(goranPanelID, 70); err != nil {
		t.Fatal(err)
	}
	if got := m.GetState().Devices[0].CurrentPercent; got != 70 {
		t.Fatalf("got %d", got)
	}
	go m.watchGoranPanel()
	defer close(m.stopChan)
	// Simulate a key using the same saved state after its verified hardware write.
	if err := os.WriteFile(b.stateFile, []byte("45\n"), 0600); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(3 * time.Second)
	for m.GetState().Devices[0].CurrentPercent != 45 {
		if time.Now().After(deadline) {
			t.Fatal("keyboard brightness did not reach DMS")
		}
		time.Sleep(20 * time.Millisecond)
	}
	// A failed helper must return an error and restore the last confirmed value.
	b.helper = filepath.Join(t.TempDir(), "missing")
	if err := m.SetBrightness(goranPanelID, 80); err == nil {
		t.Fatal("accepted failed write")
	}
	if got := m.GetState().Devices[0].CurrentPercent; got != 45 {
		t.Fatalf("failed write left %d", got)
	}
}
