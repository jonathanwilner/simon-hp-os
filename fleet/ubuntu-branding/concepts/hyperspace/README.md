# HP circle to HP-OS: selected motion

One continuous reveal follows the requested brand sequence:

- 0–1.4 s: the original circular HP logo appears with an electric-blue glow.
- 1.4–3.7 s: the circle travels continuously into the O of HP-OS. The inner HP resolves into the HP letters. HP Forma DJR Office Medium provides the typography.
- 3.7–5.4 s: HP-OS holds once, clearly readable.
- 5.4–8.4 s: the O expands into a glowing portal while the starfield accelerates and the modern four-stroke HP logo appears.
- 8.4–12 s: star travel eases down around the modern HP logo.

The circle retains one continuous geometry through both transformations. Position, scale, opacity and star speed use quintic easing. A crisp core sits above two scales of blue optical bloom. The hero video has no repeated HP-OS labels, simulated authentication, captions or extra controls.

Run with the brand kit's Python environment containing Pillow and NumPy:

```sh
python render.py --preview
python render.py
python verify.py
python render.py --native
```

Output defaults to `~/Videos/hp-logo-morph-v3`; set `HP_MOTION_OUTPUT` to change it. `HP_BRAND_ASSETS` defaults to the local authorized pdf-ppt-kit assets. Private font binaries are never copied into public source. The native export uses the same transparent hero at 480×200 and 30 fps, compressing the reveal to six seconds. Native runtime must use real boot/authentication signals and never delay completion to finish the animation.

The circular logo and original white HP forms come from the authorized `logo_HP_Electric_Blue_keyline.png`. The modern four-stroke mark reuses the exact existing polygon geometry from the original motion study, sourced from https://commons.wikimedia.org/wiki/File:HP_alternatives_Logo_2016.svg (which attributes HP Brand Central). Designer reference: https://movingbrands.com/work/hp-business-design/. Preserve its 777:999 aspect ratio. The user explicitly requested the circle-to-O animation; this is a deliberate transition, with the settled modern logo retaining its original geometry.

The delivered movie is silent, 1920×1080, 60 fps and 12 seconds. A full decode and a continuous star-speed boundary check run in `verify.py`. Concept playback is separate from native renderer and physical boot acceptance.
