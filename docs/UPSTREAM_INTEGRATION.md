# Selective upstream integration

Source: [avanza-git/nx2android-revilhd](https://github.com/avanza-git/nx2android-revilhd/tree/5e4ea3b5953944163987ecc2752258e551c3ba06), pinned at `5e4ea3b5953944163987ecc2752258e551c3ba06` on 2026-11-11.

The original local export and this revision shared 1,822 identical files. Integration uses selected source changes because the fork lacks the local Resident Evil profile and runtime features. `EXPORT_MANIFEST.json` remains the historical record of the initial export, not a manifest of subsequent integrations.

## Imported behavior

- Shader product validation checks bounded SPIR-V structure, stage identity, reflection and expected/omitted inventories. Content receipts validate the translator directory, shader bundle and report before reuse. Changed inputs or damaged products trigger regeneration. Unsupported shaders remain explicit in the report and reuse message.
- Resumed ADB transfers verify retained chunks by checksum, resend unverified chunks, and assemble only the current source's chunks. Source truncation stops before assembly.
- `python -m porter host` rebuilds an installed port's runtime, retaining the APK's driver, other entries, signing identity and game data. Profile header identity and rewrite-source checks reject incompatible ports. New data packs record optional `profile_h`; old packs still install normally but require a full port before host updates.
- Handheld/Docked switches notify both controller-style events. The local door-skip input hook remains active.
- Unsupported 32-bit inputs receive an early diagnostic. Unexpected build errors save a traceback; GUI reporting includes the relevant frame and filters frozen-launcher noise.

## Local adaptations and exclusions

The fork's GUI error-reporting change contained a malformed list comprehension; it was corrected and covered with regression tests. Imported tests use `RE_NATIVE_HOME`, preserving isolated desktop settings and signing keys.

Resident Evil profiles, observation gates, save support, door skipping, frame limits, movie timing, Picture controls, texture fixes, performance tools and branding are retained. Unrelated game profiles, sparse-texture changes, iOS-specific changes, precompiled translator binaries, agent configuration and publishing workflows were excluded during the selective integration.

## Source repository

At the user's request, this source-only snapshot is based on the fork's existing `main` history, with `origin` set to `https://github.com/avanza-git/nx2android-revilhd.git`. Publication uses a normal fast-forward commit. Files omitted by the original local export, including precompiled translators, agent configuration, unrelated game screenshots and release workflows, are removed from the published source tree; they remain available in the parent revision. The original export manifest remains unchanged.

## Validation boundaries

See [VALIDATION.md](VALIDATION.md) for measured results. Host-update tests substitute the NDK build and device transport while exercising APK rebuilding and signing. Shader checks are bounded structural and inventory checks, not full semantic SPIR-V validation. File receipt reuse uses metadata as a fast path; on Windows, a same-size change that restores the original mtime is outside that check's guarantee.

No game APK build, device installation or gameplay validation was performed. This integration makes no additional device compatibility claim.
