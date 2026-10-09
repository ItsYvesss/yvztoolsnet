# YVZTOOLS NetMath Space - v4.0

## Install / update (users)
1. Download the installer from the [latest stable release](https://github.com/ItsYvesss/yvztoolsnet/releases/latest/download/YVZTOOLS-INSTALLER.exe), or download both `YVZNETMATH.exe` and `YVZUPDATER.exe` from the release assets.
2. Run `YVZTOOLS-INSTALLER.exe` for a fresh install or upgrade, or place the app and updater in the same folder.
3. Start `YVZUPDATER.exe` to open the updater window. It checks the latest stable GitHub release, shows your installed and latest versions, and lets you choose **Update Now** when an update is available. If you are already up to date, the window stays open and tells you so; close it and open `YVZNETMATH.exe` normally.

### Someone has an old version (or an old zip)?
Run the latest installer and select the same installation folder to replace the old application and updater while preserving other files and settings. Alternatively, put the newest `YVZUPDATER.exe` in the same folder as `YVZNETMATH.exe` and run it.
A missing `version.txt` is treated as an old installation, so the updater offers the latest stable release.

## Publish a new version (you)
1. Update `APP_VERSION` and `DISPLAY_VERSION` in `version.py`, and update the Windows metadata files.
2. Create a matching tag (for example, `v4.1` for `APP_VERSION = "4.1.0"`) and push it.
3. The tag workflow builds the app, updater, and installer, then attaches all three EXEs to the release.
