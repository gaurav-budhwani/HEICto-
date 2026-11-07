#!/usr/bin/env bash
# ==============================================================================
# Install macOS Finder Quick Action for HEICto-
# Adds "Convert to PNG (HEICto-)" to macOS Finder right-click context menu.
# ==============================================================================

set -e

SERVICE_NAME="Convert to PNG (HEICto-)"
WORKFLOW_DIR="$HOME/Library/Services/${SERVICE_NAME}.workflow"
CONTENTS_DIR="${WORKFLOW_DIR}/Contents"

mkdir -p "${CONTENTS_DIR}"

# Create Info.plist
cat << 'EOF' > "${CONTENTS_DIR}/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSBackgroundColorName</key>
			<string>background</string>
			<key>NSBackgroundStrokeColorName</key>
			<string>line</string>
			<key>NSIconName</key>
			<string>NSTouchBarColorPickerFill</string>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>Convert to PNG (HEICto-)</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
			<key>NSRequiredContext</key>
			<dict>
				<key>NSApplicationIdentifier</key>
				<string>com.apple.finder</string>
			</dict>
			<key>NSSendFileTypes</key>
			<array>
				<string>public.image</string>
				<string>public.heic</string>
				<string>public.heif</string>
				<string>public.avif</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
EOF

# Create document.wflow
cat << 'EOF' > "${CONTENTS_DIR}/document.wflow"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>523</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<false/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.path</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>1.0.2</string>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key>
					<dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.path</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
					<string>SRGB="/System/Library/ColorSync/Profiles/sRGB Profile.icc"
COUNT=0

for f in "$@"
do
    ext="${f##*.}"
    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    base="${f%.*}"
    out="${base}.png"

    # Avoid overwriting
    if [ -f "$out" ]; then
        out="${base}_converted.png"
    fi

    if [ -f "$SRGB" ]; then
        /usr/bin/sips -s format png -m "$SRGB" "$f" --out "$out" >/dev/null 2>&1
    else
        /usr/bin/sips -s format png "$f" --out "$out" >/dev/null 2>&1
    fi

    COUNT=$((COUNT + 1))
done

if [ $COUNT -gt 0 ]; then
    /usr/bin/osascript -e "display notification \"Converted $COUNT photo(s) to lossless PNG with true color!\" with title \"HEICto-\""
fi
</string>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/zsh</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key>
				<string>1.0.2</string>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>B6B1F9F6-71A2-4FA3-883A-DF9F7E803362</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>OutputUUID</key>
				<string>9F8A8812-3D79-4A92-BF22-5F2D6B5EE739</string>
				<key>UUID</key>
				<string>98B6C7C8-D059-4E65-83FF-0EF7603B6432</string>
			</dict>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
EOF

echo "✅ Installed Finder Quick Action: '${SERVICE_NAME}'"
echo "👉 You can now right-click any image in Finder -> Quick Actions -> '${SERVICE_NAME}'"
