# No Hassle AV for Home Assistant

Control a No Hassle AV 8×8 HDMI matrix from Home Assistant: choose the input
for each output, send one input to every output, and switch the matrix on or off.

> **Upgrading from 0.2.x or 0.3.x?** Read [Upgrading](#upgrading) first. This
> integration is the HDMI matrix only, under the `nohassle_av` domain. The
> amplifier is its own integration,
> [No Hassle AV Amplifier](https://github.com/EndOfTheLine-HA/ha-nohassle-amp).

## What you get

- **Eight output selectors** with your own input names, showing the
  **device-reported** route from `/all_dat.get`, checked every 15 seconds,
  including changes made by another controller.
- **Outputs: All**, after Output 8, sends the chosen input to all eight outputs
  with one command. It shows a source only when all eight reported routes agree.
- **Power on** and **Power off** buttons that send explicit commands without
  assuming the current power state.
- A status failure marks the selectors unavailable rather than showing an old
  command as current feedback. Replies are size-capped and strictly decoded, so
  a corrupted or unexpected response fails the poll instead of being trusted.

Tested with the No Hassle AV eight-input, eight-output matrix that uses the HTTP
`/video.set` protocol. Other models and protocols have not been verified. Reboot
and factory reset are not exposed.

## How the matrix reports routing

The matrix answers the status request with `none` almost every time, and sends its
full routing report once after a route changes. Home Assistant therefore polls
every 15 seconds and also polls a few times right after any command it sends. Two
things follow from this:

- After a Home Assistant restart the selectors show **Unknown** until the next
  route change, because the matrix has nothing to report until then.
- The matrix closes its connection after every reply. The integration retries a
  request once when it hits a connection the matrix already closed, so a route
  change no longer makes the matrix show as unavailable (fixed in 0.3.1).

## Power

The **Power on** and **Power off** buttons send an explicit command. No reliable
power feedback was found over HTTP: on the tested unit the status page read `none`
while the matrix was on and while it was off (checked on 2026-10-24 by switching
power off and on from Home Assistant). The **Power** sensor therefore stays
**Unknown** by design, and **Unavailable** means a status read failed, not that
the matrix is off. Only HTTP is used; the matrix's RS-232 port was not tested.

Measured on the tested unit, so treat these as observations from one unit:

- After either button, the matrix answers the next status request with something
  that is not a routing report.
- Power on also takes the matrix's web server down for 8 to 45 seconds. It still
  answers ping.

For 60 seconds after the matrix accepts a power command, a failed status read is
treated as expected: the selectors and the Power sensor keep the last known data
and nothing is logged above debug level. This applies only if the matrix answered
the poll before. After the 60 seconds, a failed read makes them unavailable again.
A power command that times out does not open this window, even if the matrix
received it. Before 0.4.0, every press made the selectors and the Power sensor
unavailable for about 15 seconds and logged an error.

In one test the routes read differently after power was switched off and on
again, so check your outputs after you power the matrix on.

## Install

1. In HACS, open **Custom repositories** and add
   `https://github.com/EndOfTheLine-HA/ha-nohassle-av` as an **Integration**.
2. Download **No Hassle AV**, then restart Home Assistant.
3. Open **Settings > Devices & services > Add integration > No Hassle AV**.
4. Enter the matrix's hostname or IP address, its HTTP port and eight distinct
   input names. Setup saves the address without switching any output.

Rename the output entities to match your rooms. Home Assistant **2026.9.4 or
newer** is required.

## Upgrading

**From 0.3.x:** update in HACS and restart Home Assistant. If the import to 0.3.x
finished, entity IDs, names and history stay as they are. Check first that the
matrix and its entities work. 0.4.0 cannot finish an import that was interrupted;
if the log says an import may not have finished, install 0.3.2, restart, then
update again.

**From 0.2.x or earlier:** those versions shipped as `custom_components/monoprice`
and replaced Home Assistant's built-in Monoprice integration, which the HACS
default catalog does not accept. Versions 0.3.0 to 0.3.2 moved the matrix to the
`nohassle_av` domain and could import the old entry. 0.4.0 removes that import, so
this integration no longer touches another integration's entities or config
entries. To keep your entity IDs and history:

1. Make a full Home Assistant backup.
2. In HACS, open **No Hassle AV**, choose **Redownload** and pick **0.3.2**.
3. Restart Home Assistant, then open **Add integration > No Hassle AV** and
   choose **Import the existing matrix**.
4. Check that the outputs and buttons still have their old entity IDs, then
   update to 0.4.0.

If you would rather start clean, remove the old Monoprice entry and add the matrix
by address. The entity IDs will be new.

The amplifier, with its bass, treble and balance controls, is the separate
[No Hassle AV Amplifier](https://github.com/EndOfTheLine-HA/ha-nohassle-amp)
integration. Its README covers its own setup. The temporary
ha-monoprice-tone-controls repository is retired; uninstall it in HACS if you
installed it.

## Development and validation

See [AUDIT.md](AUDIT.md). CI runs the tests on Home Assistant 2026.9.4 and
2026.10.2, plus Ruff, HACS validation and Hassfest. Tests use simulated HTTP
responses and real Home Assistant registries, with no hardware commands.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
