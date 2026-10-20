# Audit and compatibility decision

## Privacy boundary

A private Home Assistant installation was used only to verify compatibility and
protocol behavior. This repository intentionally excludes personal names, network
addresses, credentials, configuration-entry identifiers, room/source labels,
entity inventories, helper names, network-scan results, and private configuration.

## Amplifier compatibility

The combined integration retains the `monoprice` domain, original entry version
and data shape, entity and device identifier formulas, and service names. Existing
entries default to amplifier mode. This avoids unnecessary entity duplication and
automation migration for users of the compatible Home Assistant integration.

The amplifier platforms use `pymonoprice==0.6.1`. EQ values use the player's
cached zone status rather than additional serial polls. Source-name options remain
editable, and duplicate connections to the same amplifier are rejected.

## Matrix protocol

The matrix implementation uses the device's documented-style HTTP command format
and a read-only status endpoint. Output and input values are validated before use.
A shared poll supplies selector state; malformed, incomplete, or failed responses
make feedback unavailable rather than assuming a command succeeded.

Power commands are explicit buttons. The firmware's `none` response is not treated
as proof of standby, so the Power sensor remains unknown until reliable power-state
feedback is established. Reboot and factory-reset commands are not exposed.

## Safety and validation

Automated tests use simulated serial and HTTP responses and issue no hardware
commands. CI runs Home Assistant tests, HACS validation, and Hassfest. Installing
the integration does not rewrite a user's helpers, scripts, dashboards, or
automations.

## Provenance

The amplifier base derives from the Apache-2.0 Home Assistant Core Monoprice
integration, with compatible EQ additions. See [NOTICE](NOTICE) for attribution.
