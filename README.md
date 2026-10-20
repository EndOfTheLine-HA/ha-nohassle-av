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
  Other No Hassle AV models and protocols have not been verified.

Matrix selection shows the **last command accepted over HTTP**, not confirmed
hardware feedback. Changes made with a remote or another controller will not
appear automatically. Power buttons send explicit commands without assuming the
current power state. This version does not expose reboot or factory reset.

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
switch them over. They do not automatically synchronize with the new selectors.

## Development and validation

See [AUDIT.md](AUDIT.md) for the findings and compatibility choices. CI runs HA
tests, HACS validation, and Hassfest. Tests use simulated services and HTTP
responses, with no hardware commands. Physical validation of the combined
integration remains to be done before a production rollout.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
