# Security

This repository contains code that writes to machine firmware and, in the
upstream design, to BMC fan controllers. It is research code and it is used
on hardware the reader owns. There is no formal CVE process here, and no
claim of coordinated disclosure — but there is a reporting channel for the
things that matter.

## What to report privately

Report privately, through a private issue, anything that touches a machine's
actuator:

- the ASUS thermal-policy write path (`controller/`), including the
  `DEVS` device writes, the baseline capture and restore, and the watchdog;
- any BMC or IPMI command that sets fan duty;
- the restore path, and any way to reach a state where the baseline is not
  restored;
- anything in `controller/fan-scan/` that leaves the machine in a state other
  than the one it found.

To open a private issue, use **New issue → New security advisory** on this
repository. If that option is not shown, the owner has not enabled private
vulnerability reporting yet; in that case open a normal issue that contains
no exploit detail and ask for a private channel.

## What to report publicly

Ordinary bugs are ordinary issues. Use the bug report template for:

- arithmetic errors in `code/`, including the audit;
- documentation that disagrees with the code;
- a modelling error that does not involve executing anything.

## What is out of scope

- Vulnerabilities in upstream projects. Report those to the upstream project:
  - [quiet-lab](https://github.com/0xAlcibiades/quiet-lab) — the fan
    controller this repo borrows its EKF, MPC and IPMI structure from;
  - LibreHardwareMonitor, PawnIO, and the ASUS `asus-wmi` driver.
- Physical harm from overclocking, undervolting, or disabling fan control.
  Those are decisions an operator makes about their own hardware.
- The absence of a warranty. None is offered.

## Supported versions

The code is versioned with the repository, not released separately. Only the
current `main` branch is maintained. There are no backports.

## What the maintainer will do

1. Acknowledge the report.
2. Reproduce it, or say why it cannot be reproduced.
3. Fix it, or say why the behaviour is intended — in which case the
   documentation should say so, because that is where a surprising safety
   behaviour belongs.
4. Credit the reporter, unless they ask not to be credited.
