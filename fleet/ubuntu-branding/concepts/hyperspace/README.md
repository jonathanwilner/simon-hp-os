# HP logo motion studies

Five revised 12-second, 1920×1080, 60 fps concept videos. These are designed
previews with a simulated sign-in transition, not recordings of physical boot
or successful authentication. They do not change boot, PAM or desktop settings.

## Branding and type

The official electric-blue keyline HP logo is the primary identifier throughout.
Its complete geometry, color and aspect ratio stay intact. No circle is detached
from the logo, and no letter strokes are stretched into another logo. The logo
has clear space during both the reveal and login prompt. Visible controls use
ordinary task wording; repeated HP-OS titles and footers are removed.

HP Forma DJR Office Medium is used for the welcome and sign-in headings, and
Regular for controls and supporting copy. These are the preferred typefaces in
the authorized brand kit, with the lighter presentation appropriate for a modern
system interface. Proprietary font binaries and source logo files are referenced
locally and remain outside this public renderer directory.

## Choreography

- 0–1.35 s: the intact HP logo fades in over a quiet space background.
- 1.35–3.3 s: the logo moves and scales to the login position using quintic easing.
- 2.5–3.6 s: the login controls settle into place. The center stays quiet.
- 3.6–6.65 s: the prompt holds with slow peripheral star motion.
- 6.65–9 s: the concept advances automatically. Controls fade out while the logo
  returns to center and stars accelerate continuously.
- 9–12 s: the welcome state settles. Star speed eases down without a cut.

Position and opacity use quintic smootherstep, with zero velocity and acceleration
at the joins. Star position integrates the same smooth speed ramps analytically.
The export is 60 fps, so smooth motion does not depend on frame interpolation.
Atmospheric rings, arcs and stripes are separate from the trademark.

| Study | Difference |
| --- | --- |
| Orbital aperture | Restrained blue portal and balanced radial flight. |
| Prism fold | Two quiet diagonal light lines, cooler atmosphere, slightly faster flight. |
| Ion vortex | Muted teal accents, peripheral arcs and gentle rotation. |
| Silver slipstream | Sparse silver stars and the calmest flight; no portal decoration. |
| Blue supernova | Electric-blue atmosphere, secondary outer pulse and the fullest flight. |

Orbital aperture is the balanced default. Silver slipstream is the quietest option.
The variants preserve a consistent logo and login layout.

## Reproduce

Use Python 3 with Pillow and NumPy, and FFmpeg with libx264:

```sh
python render.py --preview
python render.py                 # all five videos
python render.py --variant 1     # one video
python verify.py                 # full decode, stream metadata and encoded contact sheet
```

The default brand kit is `/home/jonathan/src/pdf-ppt-kit/assets` and may be changed
with `HP_BRAND_ASSETS`. Default output is `~/Videos/hp-logo-motion-v2`, configurable
with `HP_MOTION_OUTPUT`. Both Regular and Medium HP Forma fonts must be available
in `fonts/ttf/`, plus the canonical logo under `logos/`. Export streams frames to
FFmpeg and does not leave a large intermediate frame sequence. Previous videos
remain in their earlier directory and archive versions.

Use `nom-tmux` for rendering and full verification. Publish reviewed contact
sheets and finished videos through the private gallery/library workflow. The
native SDDM theme must use actual authentication signals; never copy the demo's
automatic advance into real login or impose a minimum boot duration.
