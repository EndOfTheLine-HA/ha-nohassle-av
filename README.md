# No Hassle AV for Home Assistant

Control a No Hassle AV 8×8 HDMI matrix from Home Assistant: choose the input
for each output, send one input to every output, and switch the matrix on or off.

> **Upgrading from 0.2.x?** Read [Upgrading from 0.2.x](#upgrading-from-02x)
> first. From 0.3.0 this integration is the HDMI matrix only, under the
> `nohassle_av` domain. Amplifier support moved out (see below).

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

## Known bug: matrix Power sensor reports Unknown

The **Power** sensor does not yet report the actual on/standby state. The
firmware can return `none` while the matrix is on, so that response cannot
safely be read as standby. The sensor therefore shows **Unknown** instead of
guessing; **Unavailable** means a status read failed, not that the matrix is
off. The **Power on** and **Power off** buttons work. Testing the matrix's
RS-232 port for a real power-status query is planned; nothing is confirmed yet.

## Install

1. In HACS, open **Custom repositories** and add
   `https://github.com/EndOfTheLine-HA/ha-nohassle-av` as an **Integration**.
2. Download **No Hassle AV**, then restart Home Assistant.
3. Open **Settings > Devices & services > Add integration > No Hassle AV**.
4. Enter the matrix's hostname or IP address, its HTTP port and eight distinct
   input names. Setup saves the address without switching any output.

Rename the output entities to match your rooms. Home Assistant **2026.9.4 or
newer** is required.

## Upgrading from 0.2.x

Versions before 0.3.0 shipped as `custom_components/monoprice`, which replaced
Home Assistant's built-in Monoprice integration and handled both the amplifier
and the matrix. That made it ineligible for the HACS default catalog, which does
not accept integrations that override a core integration. From 0.3.0:

- **The matrix** lives here, in the `nohassle_av` domain. It is moved
  automatically, keeping its entity IDs, history, names, area and disabled
  entities.
- **The amplifier** is handled by Home Assistant's built-in **Monoprice 6-Zone
  Amplifier** integration again. Your existing amplifier entry and zone entities
  are reused as they are.
- **Bass, treble and balance** are not part of Home Assistant's built-in
  integration yet. To keep them, install the temporary
  [Monoprice tone controls](https://github.com/EndOfTheLine-HA/ha-monoprice-tone-controls)
  repository, which also keeps your existing tone-control entities as they are.
  A pull request to add tone controls to Home Assistant itself is planned; once
  it ships, that repository is no longer needed.

**Steps:**

1. Make a full Home Assistant backup.
2. In HACS, update **No Hassle AV** to 0.3.0. If `custom_components/monoprice`
   is still present afterwards, remove it.
3. If you want bass, treble and balance, add and install the
   [Monoprice tone controls](https://github.com/EndOfTheLine-HA/ha-monoprice-tone-controls)
   repository now.
4. Restart Home Assistant.
5. **If you installed the tone-controls repository,** your matrix is imported
   automatically. **Otherwise,** open **Add integration > No Hassle AV** and
   choose **Import the existing matrix**.
6. Check that your matrix outputs and buttons still have their old entity IDs.

Between steps 2 and 4, entities may briefly show as unavailable or "no longer
provided". **Do not delete them;** they come back once the step above completes.
If the old matrix entry cannot be removed automatically, the log says so and it
can be deleted from **Settings > Devices & services** after the import.

## Development and validation

See [AUDIT.md](AUDIT.md). CI runs the tests on Home Assistant 2026.9.4 and
2026.10.2, plus Ruff, HACS validation and Hassfest. Tests use simulated HTTP
responses and real Home Assistant registries, with no hardware commands.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
