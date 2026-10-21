# Contributing

Everything here runs offline, on Windows or Linux, with no dependencies
outside the Python standard library.

## 1. Run the tests

There is no test framework. Every module that has anything to test carries a
`--selftest` flag, and the flags are the tests.

```powershell
uv run --no-project python code/fanlaw.py --selftest                 # 15 checks
uv run --no-project python code/cycling.py --selftest                # 17 checks
uv run --no-project python code/case.py --selftest                   # 16 checks
uv run --no-project python code/targets.py --selftest                # 12 checks
uv run --no-project python code/lambda_case.py --selftest            # 13 checks
uv run --no-project python code/together_case.py --selftest          # 16 checks
uv run --no-project python code/modal_case.py --selftest             # 17 checks
uv run --no-project python code/portfolio.py --selftest              # 10 checks
uv run --no-project python code/throughput.py --selftest             # 21 checks
uv run --no-project python code/server_thermal_controller.py --selftest  # 16 checks
```

`uv run --no-project` runs the scripts without creating a project
environment. `uv run python code/...` works as well; there is no
`pyproject.toml` in this repository and no third-party Python dependency.

`code/fleet_model.py` has no `--selftest` flag. It is a printed report, not a
checked one.

## 2. Run the audit

```powershell
uv run --no-project python code/audit.py
```

The audit is the verification entry point. It recomputes the headline numbers
in `Decimal` from first principles, compares the case modules against that
reference, checks scaling invariants, checks that invalid inputs raise,
reproduces the upstream 120 W → 15 W measurement instead of extrapolating it,
checks the fatigue provenance against the cycle simulator, checks that the
throughput term is actually debited, and finally checks that the documents
still agree with the code.

It prints one summary line:

```
0 hard failure(s), 0 warning(s)
```

- **Hard failures** mean the arithmetic or the code is wrong. The audit exits
  1 and CI goes red.
- **Warnings** are provenance statements about the model — the affinity law
  overstating the measured fan saving, `case.py`'s R=36 scenario versus the
  simulator's 1.3–1.8× range, and the throughput term. They are expected.
  `--strict` turns them into failures, and is not what CI runs.

The audit's last section checks that the documents still say what the code
says. It pins specific strings in `README.md`, `CASE-STUDY.md`,
`THREE-CASES.md` and `MODAL-CASE.md`, and it fails if any of them changes
without the check changing with it.

## 3. Code style

Match the file you are editing.

- `from __future__ import annotations` at the top of every module.
- Type hints on every function signature, including `-> None` or `-> int` for
  the entry points.
- `@dataclass` (frozen where the object is a constant configuration) instead
  of ad-hoc dicts for anything with named fields.
- `Decimal` for money in `code/audit.py`, plain `float` elsewhere. The audit
  is the independent re-derivation; it does not import the modules' helpers
  for the numbers it checks.
- Docstrings state **assumptions**, not mechanics. "Solve for the loss
  coefficient b that reproduces a measured power pair" is useful.
  "Does a thing" is not.
- No comments that restate the code. A comment earns its place by explaining
  a non-obvious intent or a physical reason.
- Errors are raised, not returned: `ValueError` for bad inputs, checked at the
  boundary of each public function.
- Line length: keep it readable at 88 columns.

## 4. Provenance is not optional

Every number in this repository carries one of four labels, and the labels are
part of the API, not decoration:

| label | meaning |
|---|---|
| **measured** | taken from this machine, from a committed artifact, or from a cited upstream measurement |
| **simulated** | produced by a model in this repo |
| **public** | published by a third party |
| **assumed** | a modelling input, named and bounded, with no measurement behind it |

Rules:

1. Never drop a label because a number is inconvenient, and never upgrade one.
2. If a number changes provenance — a modelled input becomes a measurement, or
   a measurement becomes an assumption — say so in the same change.
3. If a model input is assumed, state the value, the range it was varied over,
   and which direction the conclusion moves.
4. A number that is derived from a measurement keeps the measurement's label
   only if the derivation does not add an assumption. If it does, the result
   is at most *simulated*.

The labels live in code as fields (`NodeClass.cycling_source`,
`NodeClass.throughput_source`) and in the documents as the provenance column
of the status table. Keep the two in step.

## 5. When you change a number in a document

`code/audit.py` section 8 asserts specific strings in `README.md`,
`CASE-STUDY.md`, `THREE-CASES.md` and `MODAL-CASE.md`. If you change a number
that section checks, **update the provenance strings in section 8 in the same
pull request**, or CI will fail on a document that is correct but no longer
matches the assertion.

That section exists to stop the documentation and the code from drifting
apart. It is not a style gate; treat a red section 8 as a bug report about
your own change.

## 6. Pull requests

Fill in `.github/PULL_REQUEST_TEMPLATE.md` completely. In particular:

- which numbers changed,
- whether each changed number is measured, simulated, public or assumed,
- and whether `code/audit.py` was run, with the summary line pasted in.

Keep the diff scoped. Refactoring, renaming and reformatting belong in their
own pull request.

## 7. Reporting problems

- Model or documentation errors: open an issue.
- Anything involving a machine's actuator, a write path, or a BMC command:
  use the private reporting channel in `SECURITY.md`, not a public issue.
