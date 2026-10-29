# updatelog

## further task
- Verify the pinned-version path (`-NodeVersion v24.19.0`) end to end; only the `lts` path has been exercised.

## v1.0
- Idempotent Node.js provisioning: downloads the latest LTS (or a pinned version), verifies its SHA256 against the official SHASUMS256 file, extracts it, then rebuilds the user PATH and `.npmrc`.
- Handles the "only C: was reinstalled" case: if the runtime is still on the data drive it skips the download and just repairs PATH and npm config.
- Layout paths (runtime home, npm prefix, npm cache) are parameters with defaults rather than hard-coded constants, so the tool is usable outside the layout it was written for.
- Drops a stale legacy PATH entry left over from an older npm prefix location.
