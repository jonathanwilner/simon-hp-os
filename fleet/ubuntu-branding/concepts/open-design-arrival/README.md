# Open Design comparison: Arrival

An interactive design prototype using Open Design's official **motion-design** skill, upstream revision `87a4f91c308170a8270458fc40fc66a86ed69aac`, and a project `DESIGN.md`. This is the documented filesystem-backed agent workflow. It does not claim that Open Design's daemon, cloud service or automatic generation API ran.

Sources: [Open Design workflow](https://github.com/nexu-io/open-design#quick-start), [motion-design skill](https://github.com/nexu-io/open-design/blob/87a4f91c308170a8270458fc40fc66a86ed69aac/skills/motion-design/SKILL.md).

Serve this directory with a local HTTP server, then open `index.html`. Copy a privately licensed HP Forma DJR Office Regular font to `assets/HPForma-Regular.ttf` for exact typography. This font is intentionally excluded from public source. The HTML falls back to Arial. GSAP 3.14.2 is included with its upstream license header. The backdrop is the same image-generated asset as the native theme, so the comparison focuses on composition and motion.

The page is a design preview. Its password field, sign-in button, session switch and power control do not authenticate or modify the host. The input is cleared when preview sign-in is pressed. No data is transmitted.

## Current logo-led revision

The 8 Nov revision uses the approved HP keyline logo, HP Forma Medium headings,
Regular controls, overlapping sine-eased entrances and quintic star travel.
The native QML version follows the same visual hierarchy while retaining real
authentication, errors, user/session selection, keyboard navigation and power
confirmation. The browser remains a simulated design preview.

Serve the repository root so the canonical logo path resolves. Supply the
licensed Medium font privately at `assets/HPForma-Medium.ttf` as well as Regular.
The fallback sequence is Inter, Arial, sans-serif. Do not commit font binaries.
