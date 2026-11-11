# Where things are: the repository (and the nxnative subtree in it), the player's own folder (settings, the APK signing key).
import os, sys
from pathlib import Path

REPO = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent   # the bundle: nxnative/ beside nx2android.exe
NXNATIVE = REPO / 'nxnative'
DM = NXNATIVE / 'dm'
LOCAL_TOOLS = REPO / 'tools'   # a developer's toolchains next to the repository (not committed); the player installs their own


def user_dir():
    """The player's resident-evil-native folder: %APPDATA%\\resident-evil-native on Windows, ~/Library/Application Support/resident-evil-native on a Mac, ~/.config/resident-evil-native elsewhere.
    RE_NATIVE_HOME overrides it (tests)"""
    if os.environ.get('RE_NATIVE_HOME'): d = Path(os.environ['RE_NATIVE_HOME'])
    elif os.name == 'nt': d = Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / 'resident-evil-native'
    elif sys.platform == 'darwin': d = Path.home() / 'Library/Application Support/resident-evil-native'
    else: d = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'resident-evil-native'
    d.mkdir(parents=True, exist_ok=True)
    return d


def player_tools():   # the toolchains `porter tools --download` fetched for the player: android-ndk-r27c/, dotnet/, platform-tools/
    return user_dir() / 'toolchains'


def signing_key():   # one key per player: every app they port keeps its signer, so a new port installs over the last one
    return user_dir() / 'signing-key.json'
