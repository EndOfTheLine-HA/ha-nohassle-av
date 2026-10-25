# Audit and compatibility decision

## Privacy boundary

A private Home Assistant installation was used only to verify compatibility and
protocol behavior. This repository intentionally excludes personal names, network
addresses, credentials, configuration-entry identifiers, room/source labels,
entity inventories, helper names, network-scan results, and private configuration.
Tests use the documentation address 192.0.2.10.

## Domain change in 0.3.0

Through 0.2.x the integration used the `monoprice` domain, overriding Home
Assistant's built-in Monoprice integration so that existing amplifier entries
and entity IDs carried over. The HACS default catalog does not accept
integrations that override a core integration, so 0.3.0 splits the work:

- The HDMI matrix moves to the `nohassle_av` domain (this repository).
- The amplifier, with its bass, treble and balance controls, moves to the
  separate `ha-nohassle-amp` repository (domain `nohassle_amp`). It imports an
  existing amplifier entry, so zones and tone controls keep their entity IDs.
  The temporary `ha-monoprice-tone-controls` repository bridged the gap and is
  retired.

## Matrix migration, removed in 0.4.0

Versions 0.3.0 to 0.3.2 could import a matrix set up under the old `monoprice`
domain, moving its device and entities into `nohassle_av` and removing the old
config entry. 0.4.0 removes that code. Nothing in this repository now reads, moves
or removes another integration's config entries, devices or entities, and
`tests/test_structure.py` fails if the package mentions the old domain again.

A matrix whose import finished is unaffected: its entities keep the unique IDs
they have had since 0.3.0, which `tests/test_setup.py` pins. The 0.3.x import wrote
a `migrated_from` marker on the new entry and removed it when it finished. 0.4.0
cannot resume an interrupted import, so setup logs a warning if an entry still
carries the marker and tells the user to install 0.3.2, restart, and update again
(the marker also appears in diagnostics, which redact only the host). A user still
on 0.2.x installs 0.3.2 first, imports the matrix with it, and then updates.

## Matrix protocol

The matrix implementation uses the device's HTTP command format and a read-only
status endpoint. Output and input values are validated before use. A shared poll
supplies selector state; malformed, incomplete, oversized (over 64 KiB) or
non-ASCII responses make feedback unavailable rather than assuming a command
succeeded.

The matrix closes the connection after every reply without saying so, and reports
routing once per change (otherwise `none`). The client retries a request once when
aiohttp reports a connection the matrix already closed (`ServerDisconnectedError`
or `ClientOSError`) and never retries any other error. After a selector command the
coordinator polls up to three times, within about 1.4 seconds, and stops at the
first poll that carries a report or fails. A `none` reply keeps the previous routes
but is not counted as a report. Tests run a real aiohttp session against a fake
matrix that closes every connection.

Power commands are explicit buttons. Reboot and factory-reset commands are not
exposed.

No reliable power-state feedback was found over HTTP. On 2026-10-24 the status page
was read every 4 seconds while the matrix was switched off and on from Home
Assistant (three times each). Apart from the restart windows below, it returned
`none` throughout, including while the matrix was off, so the Power sensor stays
unknown. This is one unit, and the RS-232 port was not tested.

The same run showed two things a power command does to the status reads. The first
read after any power command did not parse as a routing report. After a power on,
the web server also stopped answering for 8 to 45 seconds (timeouts, then refused
connections, while the host still answered ping) and the first read after it
returned a full routing report. The coordinator therefore keeps the previous data
when a read fails within 60 seconds of an accepted power command, provided the
matrix was reachable on the poll before. That window is opened only after the
matrix accepts the command, so a refused or unreachable matrix still shows as
unavailable. A command that times out opens no window even if the matrix received
it, because a timeout cannot be told apart from a command that never arrived. `tests/test_power_settle.py` covers each condition, including a
Home Assistant level test of the entities' state through a failing refresh.

## Safety and validation

Automated tests use simulated HTTP responses and issue no hardware commands. CI
runs the tests on Home Assistant 2026.9.4 and 2026.10.2, plus Ruff, HACS
validation and Hassfest. Installing the integration does not rewrite a user's
helpers, scripts, dashboards or automations.

## Provenance

The matrix support was written for this repository from the user's existing HTTP
routing scripts. Code derived from Home Assistant Core's Monoprice integration
was removed from this repository in 0.3.0. See [NOTICE](NOTICE).
