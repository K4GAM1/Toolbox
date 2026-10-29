# updatelog

## further task
- Only AC settings are touched; a DC (battery) pass would make this useful on laptops.

## v1.0
- Interactive power / wireless-power tool: pick a preset or set each item, review a summary, then apply in one go.
- Covers hibernate, fast startup, sleep timeout, the hidden unattended-sleep timeout, monitor timeout, the wireless adapter power-saving mode, and the NIC's "allow the computer to turn off this device" checkbox.
- The unattended-sleep timeout is read from the registry, not `powercfg /q`, which does not print a value line for hidden settings.
- The NIC checkbox goes through the official WMI interface (`MSPower_DeviceEnable`) rather than poking the device registry keys.
- Two presets: remote / unattended, and personal power saving. The remote preset's label carries the one thing a script cannot do -- set "Restore after AC Power Loss = Power On" in the BIOS, which is what actually makes remote power-on possible.
- Absorbed a separate single-purpose script that applied exactly the remote preset's values; it had no behaviour this does not, so it was dropped rather than ported.
