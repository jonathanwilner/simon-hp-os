# HP-OS hyperspace motion studies

Five deterministic 12-second, 1920×1080, 30 fps motion concepts. These are designed
previews, not recordings of physical boot or successful authentication. The demo
automatically advances the login state. No PAM, SDDM, session or boot settings
are changed by this renderer.

## Choreography

0–1.7 s: the circular HP mark resolves with a soft halo.
1.7–3.35 s: the ring detaches and becomes the O in HP-OS.
3.6–6.4 s: a readable, quiet login form settles over a moving starfield.
6.55–9.1 s: the O expands into a portal. Stars accelerate outward. Four ribbons
resolve into the premium HP mark.
9.1–12 s: the premium mark holds as the starfield continues to travel.

| Study | Difference |
| --- | --- |
| 01 Orbital aperture | HP-blue halo, circular arc accents, direct circle-to-O path, balanced radial acceleration. |
| 02 Prism fold | The ring turns edge-on and travels over an arcing path, with a cooler halo and stronger flight. |
| 03 Ion vortex | Cyan halo, orbital lateral path, rotating starfield and dense flight. |
| 04 Silver slipstream | White-silver halo, no extra arc decoration, direct ring motion and controlled flight. |
| 05 Blue supernova | Electric-blue halo, overshooting ring, secondary portal pulse and the fastest, densest flight. |

## Reproduce

Use Python 3 with Pillow and NumPy, plus FFmpeg with libx264:

```sh
python render.py --preview
python render.py                 # all five videos
python render.py --variant 1     # one video
```

The script references the locally authorized HP brand kit at
`/home/jonathan/src/pdf-ppt-kit/assets`. It uses HP Forma DJR Office Regular and
the canonical circular logo. Proprietary fonts and image assets are deliberately
not copied into this public source. Output is written to
`~/Videos/hp-os-motion-variants` and must be privately published.

The four-stroke mark uses the exact polygon geometry of
https://commons.wikimedia.org/wiki/File:HP_alternatives_Logo_2016.svg,
which attributes its source to HP Brand Central. The original designer's account
is https://movingbrands.com/work/hp-business-design/.

The animation is intentionally silent. Frame time is deterministic. Reuse this
motion in the native login only after translating the timeline to actual SDDM
signals, bounding idle rendering, retaining keyboard/session controls, and
providing reduced motion. Do not impose a simulated wait on real boot.
