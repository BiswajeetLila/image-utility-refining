@echo off
echo Building Image Utility (Refining Enabled)...
pyinstaller --clean build.spec

echo.
echo Copying user-facing docs into dist\ImageUtilityRefining\ ...
REM Ship only ABOUT, HOW_TO_USE and a short user-facing CHANGELOG.
REM Engineering README + full CHANGELOG stay at the project root.
copy /Y HOW_TO_USE.md            dist\ImageUtilityRefining\               >nul
copy /Y dist_docs\ABOUT.md       dist\ImageUtilityRefining\               >nul
copy /Y dist_docs\CHANGELOG.md   dist\ImageUtilityRefining\               >nul

echo.
echo Build complete. Output in dist\ImageUtilityRefining\
pause
