-- Configure DMG Finder window: drag-install background + icon positions.
-- Usage: osascript dmg_finder_layout.applescript <volumeName> <appBundleName>
on run argv
	set volumeName to item 1 of argv
	set appItem to item 2 of argv

	set theXOrigin to 400
	set theYOrigin to 140
	set theWidth to 660
	set theHeight to 350
	set theBottomRightX to (theXOrigin + theWidth)
	set theBottomRightY to (theYOrigin + theHeight)

	tell application "Finder"
		tell disk volumeName
			open

			tell container window
				set current view to icon view
				set toolbar visible to false
				set statusbar visible to false
				set the bounds to {theXOrigin, theYOrigin, theBottomRightX, theBottomRightY}
				try
					set sidebar width to 0
				end try
			end tell

			set opts to the icon view options of container window
			tell opts
				set icon size to 128
				set text size to 16
				set arrangement to not arranged
				set label position to bottom
				set backgroundType to 2
			end tell

			-- HFS-relative path (required). Prefer TIFF for Finder background binding.
			try
				set background picture of opts to file ".background:background.tiff"
			on error
				set background picture of opts to file ".background:background.png"
			end try

			tell container window
				set position of item appItem to {155, 135}
				set position of item "Applications" to {455, 135}
				try
					set position of item ".background" to {theBottomRightX + 400, theBottomRightY + 400}
				end try
				try
					set position of item ".VolumeIcon.icns" to {theBottomRightX + 400, theBottomRightY + 400}
				end try
			end tell

			close
			open
			delay 2

			-- Re-apply after close/open so .DS_Store persists background + layout (create-dmg pattern).
			set opts to the icon view options of container window
			tell opts
				set text size to 16
			end tell
			try
				set background picture of opts to file ".background:background.tiff"
			on error
				set background picture of opts to file ".background:background.png"
			end try
			tell container window
				set statusbar visible to false
				set the bounds to {theXOrigin, theYOrigin, theBottomRightX - 10, theBottomRightY - 10}
			end tell
		end tell

		delay 1

		tell disk volumeName
			tell container window
				set statusbar visible to false
				set the bounds to {theXOrigin, theYOrigin, theBottomRightX, theBottomRightY}
			end tell
		end tell

		delay 4
	end tell
end run
