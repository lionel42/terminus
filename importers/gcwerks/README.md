# terminus-gcwerks

Imports the runs of a GCwerks directory into terminus. By default it imports
the standard (`std`), tertiary (`tert`) and `tank` runs, with their peak
results per compound and their flags. It reads the GCwerks files directly
with the [gcwerks](https://github.com/lionel42/gcwerks) package, so it needs
no `gcexport`, and writes through the terminus API.

```
pip install -e /path/to/gcwerks     # until gcwerks is on PyPI
pip install -e "importers/gcwerks[dev]"
```

## Usage

The server and the account come from environment variables. Use
`TERMINUS_URL`, plus either `TERMINUS_TOKEN` or `TERMINUS_EMAIL` and
`TERMINUS_PASSWORD`. The account must be a superuser.

```
# The std, tert and tank runs since 2025
terminus-gcwerks /agage/jungfraujoch-medusa --instrument jfj-medusa --from 2025-01-01

# Check everything, write nothing
terminus-gcwerks /agage/jungfraujoch-medusa --instrument jfj-medusa --dry-run -v
```

- `--from 2025-01-01 --to 2025-12-31`: the days to import. Default: all
  the years that have a results file.
- `--types std,tert,tank,air`: the GCwerks run types to import. Default:
  `std,tert,tank`.
- `--gas CFC-12 --gas N2O`: import only these gases.
- `--mode replace`: overwrite the values of runs already in terminus.
  Default: `skip`, so importing again is safe. Use `replace` after
  reprocessing or adding flags in GCwerks. The flags already in terminus are
  kept: the imported ones are added to them and the comments joined, so a
  re-import never clears a flag (also not after an `X` in GCwerks). Clear
  flags in terminus itself.
- `--no-new-compounds`: leave out the gases that terminus doesn't know,
  instead of registering them.

The instrument must already exist in terminus. For Jungfraujoch, a dry run
of 2026 takes about 5 s; of all the years since 2007, about 2 minutes.

## What it reads

| GCwerks file | What for |
|---|---|
| `results/calc/calc.<yyyy>` | the runs: time, type, port, tank, peak values, concentrations, flags |
| `config/peak.list` | the gases, in the order of the calc records |
| `data/flags`, `data/flags-range` | the flags set by hand, with their comments |
| `logs/ports.log` | the fill date and regulator of each tank; the tank of runs without one |

## How GCwerks maps to terminus

| GCwerks | terminus |
|---|---|
| run (`std.3` at 2026-01-12 20:04) | measurement of the instrument at the run time (GMT) |
| run type `std` / `tert` / `tank` | type `standard` / `tert` / `tank` (`blank2` → `blank`) |
| tank (`E-223`) | sample `e-223`, in a container `e-223` that is created if missing |
| gas (`CFC-12`) | the compound `/compounds/resolve` finds for the name |
| `area`, `ht`, `rt`, `C` | `area`, `height`, `retention_time`, `concentration` |

- **Tanks.** The tank is the one in the calc record. If that is empty, the
  importer uses the tank that `logs/ports.log` puts on the run's port at the
  run's time.
- **A tank name is one filling of a cylinder.** For example, cylinder
  ESX-3414 was filled as E-223, then refilled as E-231. So each tank becomes
  a sample, filled at:
  1. the fill date in the ports log;
  2. if there is none, the first time the tank was put on a port;
  3. if the tank isn't in the ports log, its first run.

  The container created for it is a placeholder. Move the sample to the real
  cylinder in terminus; the importer never changes a sample that already
  exists.
- **New gases.** A gas that terminus can't resolve is registered as a new
  compound. Its id is the name in lower case, with `,` replaced by `-` and
  other characters that ids don't allow replaced by `_`: `m+p-xylene` becomes
  `m_p-xylene`. The GCwerks name is added as an alias. If a compound with
  that id exists under another name, the gas is left out with a warning; add
  the GCwerks name as an alias of that compound to import it.
- **Values.** Values are float32 in GCwerks. They are sent as the shortest
  decimal that gives the same float32: `530.12`, not `530.1199951171875`.

## Flags

terminus has a bit mask of flags on each measurement (for the whole run) and
on each result (for one compound). `GET /api/v1/measurements/flags` lists
them; the importer stops if they differ from its own.

| GCwerks | terminus flag | Meaning |
|---|---|---|
| `F` | `INVALID` | rejected by hand |
| `*` | `AUTO_REJECTED` | rejected by GCwerks itself, e.g. a standard out of its tolerance |
| `B` | `NOT_IN_CALIBRATION` | on std runs: the standard isn't used in the calibration |
| `X` | clears `AUTO_REJECTED` | un-flags a value GCwerks marked `*`: the value is valid |
| `H` | `FROM_HEIGHT` | the concentration is from the peak height |
| `P` | `POLLUTION` | pollution flag |

`INVALID` and `AUTO_REJECTED` make a value unusable. The meanings of `*`,
`B` and `X` were inferred from the Jungfraujoch data, not from GCwerks
documentation. To change the mapping, edit `GCWERKS_FLAGS` in
`src/terminus_gcwerks/convert.py`, then import again with `--mode replace`
(it adds flags; flags to remove must be cleared in terminus).

Where each flag goes:

- **Measurement.** The flags of the gas `all` in `data/flags` and
  `data/flags-range`, plus the four run flags of the calc record.
- **Result.** The flags of that gas in the flag files, plus the calc flags of
  that gas: the flag of the reported value (height if `H`, else area), the
  integration flag and the pollution flag. A flag that the whole run already
  has is not repeated on each result.
- **Comment.** Each flag comment starts with its GCwerks letter, e.g.
  `F: Gast` or `F: filament failure; *`.

The calc file and the flag files usually agree. The importer takes both,
because the calc file may predate the latest flag edits, or the reverse.
Flags of gases that are not in `peak.list` are ignored with a warning.

## Tests

```
pytest      # no server needed: the API is faked with httpx.MockTransport
ruff check . && ruff format --check .
```
