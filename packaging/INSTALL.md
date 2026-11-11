# Running Resident Evil Native

This project is distributed as source. Follow the [root README](../README.md#build-locally) to install Python dependencies and run `python -m gui` or `python -m porter`.

## Optional desktop bundle

Developers may create a local desktop bundle using the [development guide](../docs/DEVELOPMENT_GUIDE.md#building-the-bundle). No prebuilt bundle or APK is supplied by this source export. Internal bundle filenames remain `nx2android` for compatibility.

After building, run the executable in `dist/nx2android/`: `nx2android.exe` on Windows or `nx2android` on macOS/Linux. Keep its sibling folders together. The bundle still needs its own downloaded toolchains and your locally supplied keys and game dump.

## Configure and port

1. In **Setup**, download missing tools or configure Android NDK r27c, .NET SDK 10, and platform-tools. Select your own `prod.keys`.
2. In **Port**, choose the folder containing your Resident Evil HD 1.0.0 base-game dump. Start the port.
3. Install the generated APK and data pack using the install option with an Android device connected and USB debugging enabled, or use `python -m porter install <ResidentEvil-data folder>` from source.

Desktop settings and signing material live in the separate `resident-evil-native` application-data directory. `RE_NATIVE_HOME` overrides it. Existing nx2android settings and signing keys are not imported. Back up existing saves before changing an installation or its signing key.

Device requirements, controls, tested behavior, and limitations are listed in the [README](../README.md).
