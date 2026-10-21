# Pull request

## What changed

<!-- One or two sentences. If this is a documentation-only change, say so. -->

## Which numbers changed

<!--
List every number this pull request changes, or write "none".

    | number | before | after | provenance (measured / simulated / public / assumed) |
    |--------|--------|-------|--------------------------------------------------|
    |        |        |       |                                                  |

A number that is unchanged but whose label changed counts as a changed number.
A number that is newly derived from an existing one counts as a changed
number. If nothing changed, write "none" and the table can be deleted.
-->

| number | before | after | provenance |
|---|---|---|---|
|  |  |  |  |

## Measured or modelled?

<!--
State, for each changed number, whether it is:

  measured  - taken from this machine, a committed artifact, or a cited
              upstream measurement
  simulated - produced by a model in this repo
  public    - published by a third party
  assumed   - a modelling input, named and bounded, with no measurement
              behind it

If a changed number is a modelled input that now rests on a measurement,
say what the measurement is and where it is committed. If it is still an
assumption, say which value and which range it was varied over.
-->

## Was `code/audit.py` run?

<!--
Required. Paste the summary line.

    uv run --no-project python code/audit.py
    ...
    0 hard failure(s), 4 warning(s)

A pull request that changes a number in a document may also need the
provenance strings in section 8 of code/audit.py updated, in the same
pull request. Say whether you did.
-->

- [ ] `uv run --no-project python code/audit.py` was run, and the summary line is above
- [ ] Every module with a `--selftest` flag was run
- [ ] Section 8 of `code/audit.py` was updated if a checked string changed
