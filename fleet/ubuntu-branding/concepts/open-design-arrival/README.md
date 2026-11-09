# Open Design comparison: Arrival

An interactive design prototype using Open Design's official **motion-design** skill, upstream revision `87a4f91c308170a8270458fc40fc66a86ed69aac`, and a project `DESIGN.md`. This is the documented filesystem-backed agent workflow. It does not claim that Open Design's daemon, cloud service or automatic generation API ran.

Sources: [Open Design workflow](https://github.com/nexu-io/open-design#quick-start), [motion-design skill](https://github.com/nexu-io/open-design/blob/87a4f91c308170a8270458fc40fc66a86ed69aac/skills/motion-design/SKILL.md).

Serve this directory with a local HTTP server, then open `index.html`. Copy a privately licensed HP Forma DJR Office Regular font to `assets/HPForma-Regular.ttf` for exact typography. This font is intentionally excluded from public source. The HTML falls back to Arial. GSAP 3.14.2 is included with its upstream license header. The backdrop is the same image-generated asset as the native theme, so the comparison focuses on composition and motion.

The page is a design preview. Its password field, sign-in button, session switch and power control do not authenticate or modify the host. The input is cleared when preview sign-in is pressed. No data is transmitted.

## Comparison with native Plymouth/QML theme

| Aspect | Native theme | Open Design Arrival concept |
|---|---|---|
| Typography | HP Forma, left-aligned form/wordmark | HP Forma, centered reveal and centered settled wordmark |
| Motion | Wordmark/form entrance with outward stars | Wordmark holds alone, then moves upward as star flight reveals controls |
| Login layout | User/password, visible session choices and power buttons | Known-user greeting, one password field; secondary controls reduced |
| Brand emphasis | Cyan outlines and dark teal controls | HP electric-blue primary action and single accent rule |
| Runtime | Actual Plymouth and SDDM contracts | Browser prototype, simulated authentication |
| Idle behavior | Parent is adding bounded entrance/reduced motion | Animation ends at four seconds; no continuous frame loop afterward |
| Integration | Ready for native staging and boot test | Port composition/choreography to QML; keep native session/error/power behavior |

Recommendation: use Arrival's centered reveal, restrained blue action and quieter hierarchy as visual direction, while retaining the native implementation's real authentication, session selection and recovery controls. Do not run a browser as the boot/login runtime. A known-user layout still needs an explicit switch-user path in a production greeter.

Evidence was captured at 1440×900 in isolated Chromium on Armstrong. This proves the concept's appearance and deterministic timeline; it does not prove Qualcomm performance or actual login.
