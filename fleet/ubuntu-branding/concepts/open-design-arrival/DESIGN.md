# HP-OS / Arrival

Open Design functional skill: upstream skills/motion-design/SKILL.md, revision 87a4f91c308170a8270458fc40fc66a86ed69aac. Interactive prototype route. No Open Design daemon or cloud generator used.

Use existing HP Forma, electric blue #024AD8, white #F4F8FC, midnight #030914. Typography is the focal object. No imitation HP corporate logo; exact OS name HP-OS. Hardware runtime integration is a separate native Plymouth/QML implementation.

Beat map: 0–0.6s black to white wordmark; 0.6–1.6s crisp centered hold; 1.6–2.7s outward star acceleration while wordmark moves upward and settles; 2.7–3.4s login controls resolve beneath it; 3.4s+ still, quiet login. Preview sign-in triggers 0.8s forward flight and a welcome state; this is simulated, never real authentication. No fixed delay should be carried into production boot.

Use 120 deterministic projected stars. Pause idle motion to conserve energy and retain reading clarity. Respect prefers-reduced-motion. Keep authored HTML, local assets, timeline and seek method editable. HP Forma binary is private and must not enter public git.
