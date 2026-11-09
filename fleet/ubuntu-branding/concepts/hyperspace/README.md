# HP circle, HP-OS login and modern slash transition

The sequence retains the actual login stage:

- 0–1.3 s: original circular HP logo appears with an electric-blue glow.
- 1.3–3.5 s: the circle moves into the exact O glyph of HP-OS.
- 3.5–4.9 s: the completed wordmark moves above the login controls.
- 4.9–8.0 s: the preview shows password entry, a pointer click on Sign in, and Signing in feedback.
- 8.0–10.6 s: the controls fade and the starfield accelerates as the modern four-stroke HP logo appears.
- 10.6–14 s: star travel eases down around the modern HP logo.

HP-OS is laid out as one complete string in HP Forma DJR Office Medium. The O uses the font's real outer and counter contours, baseline, advance and kerning. The original circle interpolates into radial samples of those contours, blends into the exact O mask, and finishes as the whole text string rendered in one operation. A geometric ellipse is never used as the settled O. Two scales of blue optical bloom sit underneath the crisp glyphs.

Run with the brand kit's Python environment containing Pillow and NumPy:

```sh
python render.py --preview
python render.py
python verify.py
python render.py --native
```

Output defaults to `~/Videos/hp-logo-morph-v4`; set `HP_MOTION_OUTPUT` to change it. `HP_BRAND_ASSETS` defaults to the authorized pdf-ppt-kit assets. HP authorized the unmodified Regular and Medium font bundle in `../../fonts/` for HP-OS distribution.

The native export is 480×200 at 30 fps. Frames 0–105 reveal the wordmark, which remains held at frame 105 while the user logs in. Frames 106–183 form the success-only continuation. SDDM must start these continuation frames only on its real authentication-success signal. Native rendering never adds an authentication wait or simulates a successful password. Boot completion retains its actual runtime callbacks.

The circular logo and original white HP forms come from the authorized `logo_HP_Electric_Blue_keyline.png`. The modern four-stroke mark preserves the original polygon geometry and 777:999 proportions, sourced from https://commons.wikimedia.org/wiki/File:HP_alternatives_Logo_2016.svg, credited there to HP Brand Central. Designer reference: https://movingbrands.com/work/hp-business-design/.

The delivered hero movie is a silent 1920×1080, 60 fps, 14-second concept with simulated password entry and sign-in. It is distinct from an isolated native renderer recording and does not establish physical boot or real authentication acceptance. `verify.py` checks full decode, dimensions, duration and continuous star-speed boundaries. Preserve earlier published revisions.
