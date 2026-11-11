# Source export validation

Validated locally on macOS ARM64 on 2026-11-11 using Python 3.15, the host C compiler, and JDK 17. Dependencies were supplied by the existing development environment; a fresh network dependency installation was not performed.

- `python -m unittest discover -s tests`: **259 tests: 257 passed, 1 skipped, 1 error**. The error is `test_vk_copy_back.CopyBack.test_protected_pools`, whose native harness times out after 15 seconds. The same test also timed out when run against the original checkout. It is retained, not suppressed. The skipped test requires NDK Vulkan headers, unavailable in the isolated configuration.
- Resident Evil profile, frame-limit, door-skip, save, and desktop settings-isolation tests passed in that run.
- An inherited overlay test assumed the old pause-menu layout. Its failure reproduced in the original checkout. The exported test now checks the face-button row, Picture row, blank optional row, and Resume placement for the current layout; it passes.
- `python tests/arch_rules.py`: all checks passed, including uncommitted non-ignored source. This also checks every retained Android profile.
- `python devtools/source_audit.py`: passed. Checks versionable source for excluded file types, binary signatures, common credential formats, absolute personal paths, broken local Markdown file links, and dependency license files. This is a bounded static check, not a legal review or a guarantee against every possible secret format.
- CLI help and JSON profile discovery passed with isolated settings; Resident Evil retains Android package `org.nx2a.t010050f00bc1a000`.
- GUI source parsed successfully; no interactive GUI or Android device test was performed for this export. No APK or desktop bundle was built.

The source-check workflow targets Ubuntu 24.04 with Python 3.12 and JDK 17. It has not been run on GitHub. It does not upload artifacts or publish releases. The protected-memory timeout remains a known local validation limitation.

## Selective fork integration — 2026-11-11

Integrated the source groups recorded in [UPSTREAM_INTEGRATION.md](UPSTREAM_INTEGRATION.md) from revision `5e4ea3b5953944163987ecc2752258e551c3ba06`.

Validation used the existing development Python environment (Python 3.15 with project dependencies) and JDK 17 on PATH. The system Python alone lacked dependencies, and the default Java launcher could not locate a runtime; those environment issues were resolved for the measured runs below without changing project requirements.

- Before integration: **259 tests: 257 passed, 1 skipped, 1 error**, in 36.495 seconds. The error was the existing 15-second `test_vk_copy_back.CopyBack.test_protected_pools` timeout.
- After integration: **319 tests: 317 passed, 1 skipped, 1 error**, in 38.733 seconds. The same protected-memory harness timed out; the same test requiring NDK Vulkan headers was skipped. No additional failures appeared.
- All 60 added tests passed, covering shader validation and cache receipts, resumed transfers, host/APK updates, 32-bit rejection, crash logs and GUI error reporting. The Resident Evil host-update fixture includes the local movie, door and save observation gates and rejects an older rewrite lacking the game's patch record. NDK compilation and device transport are mocked in host-update tests.
- Existing Resident Evil frame-limit, door-skip, save, profile, texture-first-use and settings-isolation regressions passed.
- Native controller harnesses built for `GAME=010050F00BC1A000`: `t_hid` passed **71 checks**; `t_oe` passed **36 checks**, including operation-mode notifications.
- `python tests/arch_rules.py`: all checks passed. `python devtools/source_audit.py`: passed across **1,926 versionable files**.
- All changed Python source parsed successfully; `python -m porter host --help` exposed the package, device, jobs and JSON options.

No game APK, desktop bundle, real Android runtime build or device gameplay validation was performed. Git remotes and history were unchanged during these integration checks. The original export manifest is retained unchanged. Subsequent source publication uses the fork's existing history as described in [UPSTREAM_INTEGRATION.md](UPSTREAM_INTEGRATION.md#source-repository).
