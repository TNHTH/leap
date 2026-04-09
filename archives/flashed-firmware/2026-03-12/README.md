# 2026-03-12 Flashed Firmware Archive

## Purpose

This directory preserves the exact firmware artifact that was flashed to the Leap1 robot on `2026-03-12`, plus the local source differences that existed outside the Git repository at `/home/gwh/leap`.

## Source of Truth

- Flashed binary source path:
  - `/home/gwh/leap/下载归档/2026-03-12/leap1工具包/4.固件/leap1.bin`
- Local source snapshot path:
  - `/home/gwh/leap/firmware/leap_1_v1.1`

## Included Files

- `leap1.bin`
  - The exact binary that was reported as flashed onto the robot.
- `leap1.bin.sha256`
  - SHA256 checksum for binary verification.
- `firmware_diff/`
  - Files whose local archived source differed from repository `main` at the time of archiving:
    - `lib/AP_Config/ap_config.cpp`
    - `lib/AP_Config/ap_config.h`
    - `src/ap_borad_init.cpp`
    - `src/ap_control.cpp`
    - `src/ap_ros_transport.cpp`

## Important Notes

- These archived source files are preserved for provenance and rollback analysis.
- They should not be copied over repository `main` blindly, because they predate some fixes already present on `main`.
- `.vscode/` was intentionally not archived because it is editor-local and ignored by Git.

## Workflow

- `main` remains the clean synchronization baseline.
- Any future firmware or archive update should use a dedicated feature branch or archive branch, not direct commits on `main`.
