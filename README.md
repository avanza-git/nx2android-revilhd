# Resident Evil Native

An independent Android port project focused on **Resident Evil HD remaster**, built on [nx2android](https://github.com/shirai91/nx2android) and [nxnative](https://github.com/seedds/nxnative). The game's ARM64 code runs natively through a host runtime, with graphics translated to Vulkan.

This repository contains port source and build tools. Supply your own game files and keys locally. No game executable, game assets, compiled game shaders, APK, or keys are included. This is an unofficial project, unaffiliated with Capcom or Nintendo.

## Supported version

- Switch title `010050F00BC1A000`, base game **1.0.0** (HD remaster).
- Android ARM64 device with Vulkan and BC texture support; the recorded test device is Lenovo Legion Y700 (2023), TB320FC, Adreno 730, Android 15.
- The inherited profile records title-screen, opening mansion, movement, selected door transitions, and save/load checks. Full-game completion and other devices remain unverified. This export has not received a new device test.

## Build locally

Install Python 3.11 or later. From this project folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m porter tools --download
python -m porter config keys "/path/to/your/prod.keys"
python -m porter doctor
python -m porter port ".gamedump/ResidentEvil"
```

On Windows, activate with `.venv\Scripts\activate` instead. Put your own base-game dump in `.gamedump/ResidentEvil/` before porting. The tool downloads Android NDK r27c, .NET SDK 10, and platform-tools from their providers. Extraction and shader translation build from source; the first run needs network access for dependencies. Allow substantial free disk space for the game, extraction, build outputs, and data pack (the recorded pack is about 14.6 GB).

The output is `ResidentEvil.apk` plus `ResidentEvil-data/` beside your input. To install a completed port on a connected device with USB debugging enabled:

```sh
python -m porter install ".gamedump/ResidentEvil/ResidentEvil-data"
```

To update only the runtime of a compatible installed port, without rebuilding its game data:

```sh
python -m porter host --package org.nx2a.t010050f00bc1a000
```

This requires the original signing key, an Android NDK, and a data pack made with profile identity metadata. Older packs, changed profiles, or incompatible rewritten modules require a full port first. The command preserves the installed Vulkan driver and game data. See the [integration notes](docs/UPSTREAM_INTEGRATION.md) for source provenance and validation boundaries.

For the graphical interface, run `python -m gui`, configure tools and keys in **Setup**, then select your game folder in **Port**. Internal launcher names still use nx2android.

## Playing

- **Game → Frame rate** selects 30 FPS (default), 60 FPS, or Unlimited. Movies remain at 30 FPS; Unlimited still depends on game and display limits.
- **Game → Skip doors (+)** enables pressing Start (+) during a door animation. It is off by default; room loading still completes normally. Only selected door transitions have recorded testing.
- **Game → Save game** opens the game's save screen without a typewriter. Save export/import is also available through `python -m porter saves --help`. Keep backups; complete save compatibility has not been verified.
- The pause menu allows editing and saving on-screen control layouts.

## Settings and compatibility

Desktop settings, downloaded tools, and signing material use a separate `resident-evil-native` directory under the platform's application-data location. Set `RE_NATIVE_HOME` to override it. `NX2A_HOME` is ignored; existing nx2android settings and signing keys are not imported.

The Android package remains `org.nx2a.t010050f00bc1a000`. A fresh desktop signing key cannot update an APK signed by your previous key. Back up saves and explicitly configure signing material before replacing an existing install; do not publish that material.

Shared profiles remain for runtime tooling and regression tests. Their presence is not a support claim for this project.

## Development and source checks

```sh
python -m unittest discover -s tests
python devtools/source_audit.py
```

Tests also require a C compiler and JDK 17 or later on PATH.

See [architecture](docs/ARCHITECTURE.md), the [development guide](docs/DEVELOPMENT_GUIDE.md), and the [Resident Evil profile](nxnative/dm/games/010050F00BC1A000/android.tsv). Source CI runs tests and the export audit; it does not publish releases. Development is hosted at [avanza-git/nx2android-revilhd](https://github.com/avanza-git/nx2android-revilhd), preserving the fork's existing history. See [ATTRIBUTION.md](ATTRIBUTION.md) for the local source export's provenance.

## License and credits

Port source retains the upstream [MIT license](LICENSE). Dependencies retain their own licenses; see [ATTRIBUTION.md](ATTRIBUTION.md) and the [third-party inventory](nxnative/dm/third_party/README.md). The code license does not grant rights to Resident Evil game content or trademarks.
