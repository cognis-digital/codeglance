# Demo 01 — Basic onboarding map

## Scenario

You (or an AI agent) just cloned an unfamiliar Python project and need to know,
in seconds: what are the packages, which files are load-bearing, and how do the
modules depend on each other? CODEGLANCE answers that without running the code.

The `sample_pkg/` directory here is a tiny but realistic multi-module package:

```
sample_pkg/
  __init__.py     # re-exports the public API
  config.py       # leaf module, no internal deps
  models.py       # imports config
  service.py      # imports models + config, holds the branchy business logic
  cli.py          # imports service — thin entry point
```

`service.py` is the central, most-complex module and is imported by the most
other files, so it should rank as the #1 hotspot.

## Run it

Full map (human-readable):

```
python -m codeglance map demos/01-basic
```

Just the files to read first, as JSON (great for feeding an agent):

```
python -m codeglance hotspots demos/01-basic --format json
```

Internal dependency edges:

```
python -m codeglance deps demos/01-basic
```

## Expected

- `service.py` appears at or near the top of `hotspots` (high fan-in + complexity).
- `config.py` has fan-in but near-zero complexity (it is a leaf others depend on).
- `deps` shows edges like `sample_pkg/service.py -> sample_pkg/models.py`.
