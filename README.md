# Pushpuffin

Desktop GitHub uploader using the reusable FileFinder+ browser and your own official GitHub CLI login. Requires Python 3.10+, Tk, a desktop/VNC display, FileFinder+ installed, official `gh`, and this user's installed Pi App Store. No embedded login, password, token or vault access. No automatic dependency installs. FileFinder+ remains standalone and does not require the store.

Install the Pi App Store from https://github.com/Greenisus1/pi-app-store and FileFinder+ through its Install hook first. Store check requires `~/.local/share/pi-app-store/program/appstore.py` and an AppStore wrapper pointing to it. This is an installation check, not cryptographic attestation. FileFinder+ module is imported from `~/.local/share/filefinderplus`.

In your own terminal, use `gh auth login --hostname github.com` (official GitHub CLI browser/device login), then `python3 pushpuffin.py`. Never enter a password/token into this app. Child processes clear GH_TOKEN/GITHUB_TOKEN and related token/host overrides so they use the CLI's saved login. The CLI may itself store a token, under its own security rules. The app never reads or prints that token. No login subprocess is run automatically.

Browse folders, select files/folders, specify existing owner/repository, existing branch and optional relative destination folder. Review checks CLI account identity, repository visibility, push permission and branch tree. Final dialog shows account, public/private, branch and all staged paths/sizes. Nothing is uploaded until you click Upload these reviewed files. Selected bytes are read into memory before review, so later local changes are not uploaded. Files selected directly retain their basename; folders retain their top folder name and relative paths. Empty folders aren't uploaded. Hidden files are included except .git; check the review carefully.

Version 1.1.0 supports NEW FILES ONLY, no overwrites, deletes, repo creation or branch creation. 200 files, 10 MiB total, 2 MiB each. Symlinks/special files rejected, .git skipped; obvious secret names (.env, keys, credentials files) are blocked. This is NOT complete secret detection: secrets can be inside any ordinary file. Review contents yourself before sharing, especially to public repositories. No automatic retries. Remote identity, visibility and branch commit are rechecked before the first write. Races after that remain possible, but new-file PUTs omit SHA and do not overwrite existing files.

Uploads use gh api, one commit per file, serially. Returned blob SHA is checked against staged bytes. A failure can leave earlier files committed; the current request outcome can be uncertain after a connection failure. Check GitHub before retrying. Stop waits until the current request ends, then stops before the next file. No rollback or deletion. Branch rules, workflow permissions, network and GitHub limits may block uploads. No real GitHub writes were performed during tests; API interactions were mocked. Physical Pi/real CLI login/upload remain untested; GUI inspected under Linux/Xvfb.

AppStore hooks: `bash app-store.sh install` checks dependencies only, `bash app-store.sh run` starts the window. Version 1.1.0. Tests: `python3 -m unittest -v`.

Sources: https://cli.github.com/manual/gh_api ; https://cli.github.com/manual/gh_auth_login ; https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28 . Uses Contents PUT new-file mode, not a git push of a local checkout.

## Install repair (1.1.0)

If Tk is missing and apt-get is available while running as root, the reviewed install hook announces and installs python3-tk. Otherwise it stops with instructions. It does not install a desktop. The run hook reports missing or inaccessible DISPLAY with desktop/VNC guidance instead of a traceback.

## Terminal-first update 1.1.0

Default python3 pushpuffin.py / bash app-store.sh run uses a colored curses terminal interface over interactive SSH. No Tk or desktop is needed. FileFinder+ 1.1.0 must be installed first (terminal picker modules). Pick multiple files/whole folders, enter repo/branch/destination, review account/visibility/every staged path+size, then explicitly approve. Checks may pause while gh completes. Upload output appears in the terminal; Ctrl-C requests stop, current file may have an uncertain outcome. Check GitHub before retrying; earlier commits remain. No real upload was tested. Existing limits/no-overwrite/token handling unchanged.

Optional GUI: python3 pushpuffin.py --gui or bash app-store.sh gui. This alone needs Tk+desktop/VNC. Terminal install no longer adds Tk. The reusable FileFinder+ picker is used in both modes. Terminal uses arrows/j/k, Enter, Esc/q; prompts mask no secrets because only non-secret paths/repo details are collected. No TTY gets a clear error. 80x24 recommended. Physical Pi untested.
