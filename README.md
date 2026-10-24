# No Hassle AV for Home Assistant

Control a compatible whole-home amplifier or an 8×8 HDMI matrix from one integration.

During setup, choose **Amplifier** or **HDMI Matrix**. Add it again if you own both.

## Supported equipment

- **Amplifier:** the Monoprice-compatible six-zone protocol used by the audited
  No Hassle AV amplifier. Power, volume, mute, source, bass, treble, balance,
  and snapshot/restore. Up to three six-zone units use the existing address scheme.
- **Matrix:** the HTTP `/video.set` protocol used by the audited No Hassle AV
  eight-input/eight-output matrix. Eight output selectors with configurable input names,
  plus **Power on** and **Power off** buttons on the same device.
  **Outputs: All**, after Output 8, sends the chosen input to all eight outputs
  with one command. It shows a source only when all eight reported routes agree;
  differing or incomplete routes show unknown. You can still choose an input.
  Other No Hassle AV models and protocols have not been verified.

Matrix selection reads **device-reported routing** from `/all_dat.get` every
15 seconds, including changes made by another controller. A status failure marks
the selectors unavailable rather than showing an old command as current feedback.
Power buttons send explicit commands without assuming the
current power state. This version does not expose reboot or factory reset.
Routing reports update the selectors, and `none` retains the last device report.
After startup, inputs remain unknown until the device supplies a complete report.
A timeout or malformed response marks feedback unavailable.

## Known bugs

### Matrix Power sensor reports Unknown

The matrix **Power** sensor does not currently report the actual on/standby state.
This is a known bug, and we are working to resolve it by identifying and validating
reliable power-state feedback. There is no confirmed fix yet.

The firmware can return `none` even while the matrix is powered on, so that
response cannot safely be interpreted as standby/off. The sensor therefore shows
**Unknown** instead of guessing. **Unavailable** indicates a status-read failure,
not a confirmed power-off state. The existing **Power on** and **Power off** buttons
remain functional. This issue concerns matrix power feedback, not amplifier
power controls.

We will be testing the matrix's physical **RS-232 interface soon** to look for
and validate an actual power-status query. RS-232 power feedback has not yet
been verified or implemented; this is an investigation plan, not a confirmed fix.

## Install

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/EndOfTheLine-HA/ha-nohassle-av` as an **Integration**.
3. Download **No Hassle AV**, then restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → No Hassle AV**.
5. Choose your device type and enter its connection details.

For an amplifier, use its serial device or supported serial-over-IP address and
optionally name the six inputs. For a matrix, enter its hostname/IP, HTTP port,
and eight distinct input names. Rename output entities in HA to match your rooms.
Matrix setup saves the address without issuing a routing command; test an output
after setup when a route change is appropriate.

## Existing Monoprice installations

The internal domain remains `monoprice` to preserve existing configuration entries,
entity IDs, custom names, disabled entities, and the `monoprice.snapshot` and
`monoprice.restore` actions. An existing entry without a device type remains an amplifier.
**Keep your existing integration entry. Do not remove and recreate it.** This
custom integration replaces HA's built-in Monoprice implementation while installed.
Do not install another HACS integration that also provides `custom_components/monoprice`.

## Existing matrix scripts and helpers

Your `input_select` helpers, shell commands, and automations remain independent.
Installing this integration does not remove, rename, or rewrite them. The new
matrix selectors have new IDs in the `select` domain. Existing matrix dashboard
cards and automations continue to use their old helpers until you deliberately
switch them over. The new selectors read the matrix directly; the old helpers
remain independent and are not rewritten.

## Development and validation

See [AUDIT.md](AUDIT.md) for the findings and compatibility choices. CI runs HA
tests, HACS validation, and Hassfest. Tests use simulated services and HTTP
responses, with no hardware commands. Physical validation of the combined
integration remains to be done before a production rollout.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
