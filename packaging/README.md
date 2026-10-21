# Packaging the Windows app

`macbootsmith.spec` builds MacBootsmith as a PyInstaller onedir app: a `MacBootsmith` folder with `MacBootsmith.exe` (windowed, no console) and an `_internal` folder. PyInstaller is a build tool only; the app never imports it and runs on the Python standard library (Tkinter included).

## Build

From the repository root, on Windows with Python 3.8 or newer:

```
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean packaging/macbootsmith.spec
```

The result is `dist\MacBootsmith`. Ship the whole folder (zip it); the exe does not run on its own.

The CI job `package` (`.github/workflows/ci.yml`) does the same on `windows-latest`, then runs the packaged app twice: a headless build of the desktop fixture (`MacBootsmith.exe --headless tests/fixtures/answers-desktop.json`, exit code 0 and ocvalidate passing are required) and the window self-test (`MacBootsmith.exe --self-test`). The folder is uploaded as the `MacBootsmith-windows` artifact before those runs, so the artifact holds no downloads or results.

## What goes where

- Bundled, read-only (inside `_internal`): the Python code, `OpCore-Simplify.py`, `Scripts/usb_enum.cs`, `Scripts/datasets/background_picker.icns` and `docs/reference/*.md`.
- Written next to `MacBootsmith.exe`: `Results`, `SysReport`, `OCK_Files`, the downloaded tools in `Scripts` (Hardware Sniffer, macserial, ocvalidate, iasl, acpidump) and `MacBootsmith.log`. `Scripts/app_paths.py` makes this split: `app_dir()` is the exe folder when frozen and the repository root otherwise; `bundle_dir()` is `_internal` when frozen.
- Without a console, standard output goes to `MacBootsmith.log` next to the exe. `--headless` and `--analyze-log` work as in `OpCore-Simplify.py`; their output lands in that log.

Put the folder somewhere the user can write to (for example the Desktop or Downloads), not `Program Files`.

## Unsigned executable

The build is not code-signed; CI has no certificate. Expect:

- SmartScreen: "Windows protected your PC" on first start. Users choose More info, then Run anyway. The warning fades as a build gains reputation, and signing with a trusted certificate removes it.
- Antivirus: PyInstaller's bootloader is shared by many programs, including malware, so some scanners flag any unsigned PyInstaller build. The onedir layout, no UPX compression and an `asInvoker` manifest (the default; the exe does not ask for administrator rights) keep false positives down. If a scanner still flags it, report it to the vendor as a false positive.
- Publish the SHA-256 of the zip next to each release so users can check the download (`certutil -hashfile MacBootsmith.zip SHA256`).

Writing a USB drive needs administrator rights. The USB page offers "Restart as administrator", which relaunches the exe elevated only when the user asks for it.
