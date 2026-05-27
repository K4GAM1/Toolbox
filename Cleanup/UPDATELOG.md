# updatelog

## further task
- Add more application cache.

## v1.02
- Added post-cleanup summary screen showing total freed space and deleted item count
- Added option to return to main menu or exit after cleanup completes
- Pressing `[q]` in any menu now clears the screen and closes the terminal window
- Fixed operation flow: execution progress is cleared before displaying the results table

## v1.01
- Redesigned the welcome screen with ASCII art and rainbow coloring
- Fixed UI display logic for menu rendering and in-place redraws

## Pre-release
- Fixed an issue where recursive empty folder scanning would incorrectly remove Quick Access entries and other user-specific configuration directories under AppData
