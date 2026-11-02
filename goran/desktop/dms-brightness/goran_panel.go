package brightness

// Goran's NVIDIA eDP OLED has no sysfs backlight. Use the existing hardware
// helper, which verifies the AUX write and atomically saves its percentage.
import (
	"context"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const goranPanelID = "goran-edp"

type goranPanelBackend struct {
	helper    string
	stateFile string
}

func newGoranPanelBackend() *goranPanelBackend {
	helper := os.Getenv("DMS_GORAN_BRIGHTNESS")
	if helper == "" || !filepath.IsAbs(helper) {
		return nil
	}
	stateHome := os.Getenv("XDG_STATE_HOME")
	if stateHome == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil
		}
		stateHome = filepath.Join(home, ".local", "state")
	}
	b := &goranPanelBackend{helper, filepath.Join(stateHome, "goran-brightness", "percent")}
	// Probe the real panel once. Other N1X hosts keep normal DMS discovery.
	if err := b.run("status"); err != nil {
		return nil
	}
	return b
}

func (b *goranPanelBackend) run(args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	output, err := exec.CommandContext(ctx, b.helper, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("NVIDIA panel helper: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func (b *goranPanelBackend) percent() (int, error) {
	data, err := os.ReadFile(b.stateFile)
	if os.IsNotExist(err) {
		return 100, nil
	} // Same initial value as the helper.
	if err != nil {
		return 0, err
	}
	p, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil || p < 5 || p > 100 {
		return 0, fmt.Errorf("invalid saved panel brightness: %q", data)
	}
	return p, nil
}

func (b *goranPanelBackend) appendDevice(devices []Device) []Device {
	// NVIDIA 615 registers nvidia_0 on this OLED, but its writes clear the
	// panel's AUX luminance mode. Keep using the verified OLED helper.
	filtered := make([]Device, 0, len(devices))
	for _, d := range devices {
		if d.ID != "backlight:nvidia_0" {
			filtered = append(filtered, d)
		}
	}
	devices = filtered
	for _, d := range devices {
		if d.Class == ClassBacklight {
			return devices
		} // Prefer a future native driver.
	}
	p, err := b.percent()
	if err != nil {
		return devices
	}
	return append(devices, Device{Class: ClassBacklight, ID: goranPanelID,
		Name: "NVIDIA eDP OLED", Current: p, CurrentPercent: p, Max: 100,
		Backend: "nvidia-aux"})
}

func (b *goranPanelBackend) SetBrightnessWithExponent(id string, percent int, exponential bool, exponent float64) error {
	if id != goranPanelID {
		return fmt.Errorf("unknown NVIDIA panel: %s", id)
	}
	if percent < 0 || percent > 100 {
		return fmt.Errorf("percent out of range: %d", percent)
	}
	if exponential {
		if math.IsNaN(exponent) || math.IsInf(exponent, 0) || exponent <= 0 {
			return fmt.Errorf("invalid brightness exponent")
		}
		percent = int(math.Round(math.Pow(float64(percent)/100, exponent) * 100))
	}
	// The helper's physical range is 5..100% (10..500 cd/m²).
	return b.run("set", strconv.Itoa(max(5, percent)))
}

func (m *Manager) watchGoranPanel() {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-m.stopChan:
			return
		case <-ticker.C:
			p, err := m.goranBackend.percent()
			if err != nil {
				continue
			}
			for _, d := range m.GetState().Devices {
				if d.ID == goranPanelID && d.CurrentPercent != p {
					m.updateState() // Publish changes made by the existing brightness keys.
					break
				}
			}
		}
	}
}
