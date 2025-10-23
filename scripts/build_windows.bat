@echo off
setlocal enabledelayedexpansion
pushd %~dp0\..
pyinstaller --noconfirm --onefile --name wfmarket-cli cli.py
pyinstaller --noconfirm --onefile --name wfmarket-gui gui.py
popd
