# HP-OS star-flight direction

The corrected direction restores the original circular HP logo, the visible HP-OS identity, luminous transitions, and the modern four-slash HP logo. Reveal the circular mark, move and reshape its circle continuously into the O of HP-OS exactly once, hold the wordmark at the usable login prompt, then move into the starfield and modern logo after successful sign-in. The O must be the actual HP Forma glyph with the same weight, size, baseline and font-derived spacing as the rest of HP-OS, not a substitute ellipse. Concept videos must show the login interaction and label simulated authentication in their provenance. Use HP Forma Medium/Regular and eased position, opacity, glow and star velocity. The user explicitly requested the circle-to-O transformation. Avoid repeating HP-OS in decorative footers or adding a second reveal. Use original assets and choreography; no HarmonyOS assets are copied.

Native implementation lives in `fleet/ubuntu-branding/plymouth` and `fleet/ubuntu-branding/sddm/hp-os` in the simon-hp-os repository. The public package stages the theme; licensed HP Forma is supplied from the host at installation.

## Generated background provenance

Created with Codex built-in image generation on 8 Nov 2026. Output is `sddm/hp-os/images/starfield.png`. Text and moving stars are rendered separately.

Prompt:

> Create a refined premium operating system login background, wide 16:9 1920x1080 composition. Near-black midnight blue space with very sparse tiny crisp white and icy cyan stars. Subtle radial sense of travel toward a vanishing point centered at 50% x 46% y, only a handful of very faint fine blue-white streaks near the outer edges. Central 45 percent very dark, calm and nearly empty, to support an exact OS wordmark and login controls that will be drawn separately. Restrained HP-inspired cool blue light, clean precision, sophisticated realistic depth, no purple or magenta, no bright nebula, no planets, no spaceship, no horizon, no text, no lettering, no logos, no UI. A quiet static atmospheric foundation for separately animated hyperspace stars. Smooth near-black gradients, no noisy grain.

Primary references:
- https://motioncanvas.io/docs/rendering/
- https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
- https://glaxnimate.mattbas.org/
- https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html
- https://github.com/sddm/sddm/blob/develop/docs/THEMING.md
- https://gitlab.freedesktop.org/plymouth/plymouth
