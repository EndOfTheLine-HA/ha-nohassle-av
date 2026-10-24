# Security reports

Please do not post your matrix's address, network layout or unredacted
diagnostics in a public issue. Diagnostics remove the matrix address, but check
the file before attaching it.

For a vulnerability, contact the repository owner privately through GitHub
before public disclosure.

The integration only talks to the matrix address you configure, over HTTP, and
never exposes reboot or factory-reset commands. Any other outbound request
should be treated as a critical defect.
