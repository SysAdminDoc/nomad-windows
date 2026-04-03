#!/bin/bash
# Build an AppImage for NOMAD Field Desk
# Requires: appimagetool (from https://github.com/AppImage/appimagetool)
# Usage: ./tools/build_appimage.sh

set -e

APP_NAME="NOMADFieldDesk"
APP_DIR="$APP_NAME.AppDir"

echo "Building AppImage..."

# Clean previous
rm -rf "$APP_DIR" "$APP_NAME"*.AppImage

# Create AppDir structure
mkdir -p "$APP_DIR/usr/bin" "$APP_DIR/usr/share/applications" "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller binary (must be built first)
if [ ! -f "dist/NOMADFieldDesk" ]; then
    echo "ERROR: dist/NOMADFieldDesk not found. Run 'pyinstaller build.spec' first."
    exit 1
fi
cp dist/NOMADFieldDesk "$APP_DIR/usr/bin/NOMADFieldDesk"
chmod +x "$APP_DIR/usr/bin/NOMADFieldDesk"

# Copy icon
if [ -f icon.ico ]; then
    # Convert ico to png if possible, otherwise use as-is
    if command -v convert &>/dev/null; then
        convert icon.ico -resize 256x256 "$APP_DIR/usr/share/icons/hicolor/256x256/apps/nomad-field-desk.png"
    fi
fi
# Also copy nomad-mark.png as fallback icon
if [ -f nomad-mark.png ]; then
    cp nomad-mark.png "$APP_DIR/usr/share/icons/hicolor/256x256/apps/nomad-field-desk.png" 2>/dev/null || true
fi

# Create .desktop file
cat > "$APP_DIR/usr/share/applications/nomad-field-desk.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=NOMAD Field Desk
Comment=Offline preparedness and field operations command center
Exec=NOMADFieldDesk
Icon=nomad-field-desk
Categories=Utility;
Terminal=false
StartupNotify=true
DESKTOP

# AppImage requires desktop file and icon at root
cp "$APP_DIR/usr/share/applications/nomad-field-desk.desktop" "$APP_DIR/"
cp "$APP_DIR/usr/share/icons/hicolor/256x256/apps/nomad-field-desk.png" "$APP_DIR/" 2>/dev/null || true

# Create AppRun
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "${HERE}/usr/bin/NOMADFieldDesk" "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

# Build AppImage
if command -v appimagetool &>/dev/null; then
    ARCH=$(uname -m) appimagetool "$APP_DIR"
    echo "AppImage built successfully!"
elif [ -f /tmp/appimagetool ]; then
    ARCH=$(uname -m) /tmp/appimagetool "$APP_DIR"
else
    echo "appimagetool not found. Download from https://github.com/AppImage/appimagetool/releases"
    echo "AppDir created at $APP_DIR — run appimagetool manually."
fi
