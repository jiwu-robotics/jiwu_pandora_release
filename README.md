# JIWU-Pandora releases

Public installers for the JIWU-Pandora robot data collection client.

- Ubuntu 22.04 amd64: install the `.deb` asset with `sudo apt install ./jiwu-pandora_VERSION_amd64.deb`. Python 3.12 is included.
- Python 3.12: unpack the offline bundle and run `bash install-python.sh /absolute/path/to/venv`.
- Verify downloads using the release's SHA256SUMS.
- Stop recording/teleoperation/drag, safely support the arms, and close the client before installation.
- Existing clients: set the update repository to `jiwu-robotics/jiwu_pandora_release` in update settings; leave the token empty. Check for updates and download the verified package. Installation requires local administrator authorization.
- The Debian package identifier remains `jiwu-abc` for upgrades from older versions; the product and launch command are JIWU-Pandora / `jiwu-pandora`.

Installers are in GitHub Releases. Source development is maintained separately in the private `jiwu-robotics/jiwu_pandora` repository. Publishing a release makes it available to clients; it does not force installation on running equipment.
