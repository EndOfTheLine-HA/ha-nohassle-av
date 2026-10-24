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

## Matrix migration

A matrix entry from 0.2.x is a `monoprice` entry with `device_type: matrix`.
The import flow (started by the user from the No Hassle AV setup menu, or
earlier by the now retired tone-controls repository) creates a `nohassle_av` entry marked with the old
entry's ID. Before any platform loads, its setup:

1. Unloads the old entry if it is loaded (entities can only change integration
   while not loaded).
2. Moves each old entity to `nohassle_av` with
   `entity_registry.async_update_entity_platform`, rewriting the entry-ID prefix
   of its unique ID. Entity IDs, history, custom names and disabled or hidden
   flags are kept.
3. Moves the old device to the new entry with a single `async_update_device`
   call (`new_config_entry_id`), keeping its device ID, area and user-given
   name. Entities move first: moving a device to another config entry removes
   any of its entities still registered to the old one.
4. Removes the old entry. If that fails, the move still stands and a warning
   asks the user to delete the empty entry.

The migration is idempotent and covered by tests on real Home Assistant
registries, including mutation checks for each step's ordering and API use.

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

Power commands are explicit buttons. The firmware's `none` response is not
treated as proof of standby, so the Power sensor remains unknown until reliable
power-state feedback is established. Reboot and factory-reset commands are not
exposed.

## Safety and validation

Automated tests use simulated HTTP responses and issue no hardware commands. CI
runs the tests on Home Assistant 2026.9.4 and 2026.10.2, plus Ruff, HACS
validation and Hassfest. Installing the integration does not rewrite a user's
helpers, scripts, dashboards or automations.

## Provenance

The matrix support was written for this repository from the user's existing HTTP
routing scripts. Code derived from Home Assistant Core's Monoprice integration
was removed from this repository in 0.3.0. See [NOTICE](NOTICE).
