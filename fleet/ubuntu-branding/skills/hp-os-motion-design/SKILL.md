---
name: hp-os-motion-design
description: Design and implement HP-OS animated boot splashes and login screens using HP typography, generated backgrounds, Plymouth and Qt Quick. Use for motion concepts, star-flight transitions, reusable assets, previews and Ubuntu fleet integration. Works with Codex and DeepSeek Harness.
---

# HP-OS motion design

Deliver editable source, reproducible assets, runtime themes and a reviewed preview. Locate the consuming fleet checkout and read its AGENTS.md before editing. Preserve the active desktop and existing authentication.

## Design and assets

- Use the existing HP brand kit and licensed HP Forma font available on the host. Keep proprietary font binaries and credentials out of public source. Use the approved HP logo as the primary identity. Keep `HP-OS` text only where the product or session needs explicit identification. Use HP Forma Medium for headings and Regular for controls; never rely on generated lettering or redraw logo geometry.
- For this direction: intact approved HP logo, near-black blue space, restrained HP blue accents, quiet center and sparse stars that travel outward from a central vanishing point. Keep the password and session controls clear throughout motion.
- Generate bitmap atmosphere with the available image-generation tool. Ask for no text, logos or controls. Save the prompt, output provenance and resulting asset in the project. Draw typography and motion in code.
- Offer a distinct alternative only when requested. Label concept previews separately from actual native renderer output.

## Choose tools by output

1. **Motion Canvas:** TypeScript timeline, easing and deterministic PNG sequence export for a designed reveal. Use when choreography needs an editable timeline.
2. **Blender:** Python-driven camera and particle renders for depth-rich star flight. Bake assets offline; no Blender process at boot.
3. **Glaxnimate:** vector logo or shape animation. Export supported frames for the target renderer.
4. **Qt Quick/QML:** interactive SDDM login and authentication state transitions. Keep native text sharp. Budget software rendering explicitly.
5. **Plymouth script:** early boot sprites, progress and password prompts. Precompute sprites rather than rescaling every frame.

The current fleet implementation uses native QML and Plymouth procedural motion, with an image-generated backdrop. The authoring tools above are optional; install only those needed for the chosen design.

## Runtime contracts

- Plymouth must retain password, question, message and update callbacks. Never add a minimum boot duration or simulate progress. Keep normal boot and experimental initrd rebuilds separate and preserve candidate modules/DTBs.
- SDDM owns authentication. Use its login/failure/success signals; preserve session selection, keyboard navigation and power confirmation. Do not modify PAM or autologin for visual effects. The compositor can end the animation immediately after successful login.
- Use bounded star counts and resolution-aware layout. Provide a reduced-motion setting. Avoid full-resolution software canvas repainting when a smaller layer or scene graph sprites suffice.
- Compare at the target display resolution. Capture both the reveal and the settled prompt. Measure the animation without recording overhead.

## Review and deployment

- Preview SDDM on an isolated Xvfb display; never restart the live display manager to preview. Test Plymouth in an isolated namespace/display without claiming it proves physical boot.
- Publish screenshots and clips through the repository's evidence workflow. Review readability, logo sharpness, star direction, clipping, idle cost and error states.
- Build ARM64 and x86-64 consumers through the repository build tracker. Publish shared source before refreshing consumer locks.
- Stage theme files without ending the session. Rebuild every affected initrd using its host workflow. Preserve backups and known-good defaults. Ask for readiness before a reboot that closes user apps.
- Report source/build, isolated rendering and physical acceptance separately. A screenshot cannot prove animation or successful password login.

Read `references/design-brief.md` for the implemented direction and asset prompt.
