"""Convert GCwerks runs into terminus measurements, samples and flags.

No network here: these functions turn what the ``gcwerks`` package reads in
a GCwerks directory into the payloads of the terminus API.

* A run of ``results/calc/calc.<yyyy>`` becomes a measurement of the
  instrument at the run time (GMT). Its type is mapped by :data:`RUN_TYPES`.
* The tank of a run (in the calc record, else the tank on the run's port in
  the ports log) is a terminus **sample**: a GCwerks tank name such as
  ``E-223`` names one filling of a cylinder.
* Each gas becomes the result of a terminus compound: ``area``, ``ht``,
  ``rt`` and ``C`` (the reported concentration).
* GCwerks flags become terminus quality flags (:data:`GCWERKS_FLAGS`): the
  flags of the gas ``all`` on the measurement, the others on the result.
  The comment keeps the GCwerks letters, e.g. ``F: Gast``.
"""

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntFlag

import numpy as np
import pandas as pd
from gcwerks.io.calc import GAS_FLAGS, GAS_VALUES, Calc
from gcwerks.io.flags import ALL
from gcwerks.io.ports import tanks_on_ports

logger = logging.getLogger(__name__)


class Flag(IntFlag):
    """The terminus quality flags (backend app.models.flags.QualityFlag).

    The command checks them against ``GET /measurements/flags``.
    """

    INVALID = 1 << 0
    AUTO_REJECTED = 1 << 1
    SUSPECT = 1 << 2
    NOT_IN_CALIBRATION = 1 << 3
    POLLUTION = 1 << 4
    FROM_HEIGHT = 1 << 5


GCWERKS_FLAGS = {
    "F": Flag.INVALID,  # rejected by hand
    "*": Flag.AUTO_REJECTED,  # flagged by GCwerks itself (e.g. a standard outlier)
    "B": Flag.NOT_IN_CALIBRATION,  # on std runs only, the standard is not used
    "X": Flag(0),  # un-flags a value GCwerks flagged "*": valid
    "H": Flag.FROM_HEIGHT,  # C from the height (integration flag)
    "P": Flag.POLLUTION,  # pollution flag
}
"""GCwerks flag letter -> terminus flags."""

RUN_TYPES = {
    "air": "air",
    "std": "standard",
    "tert": "tert",
    "tank": "tank",
    "blank": "blank",
    "blank2": "blank",
    "labair": "labair",
    "test": "test",
}
"""GCwerks run type -> terminus measurement type (other run types are not imported)."""
DEFAULT_RUN_TYPES = ("std", "tert", "tank")
SAMPLE_RUN_TYPES = frozenset({"std", "tert", "tank"})
"""Run types that measure the content of a tank (they need one)."""

VARIABLES = {"area": "area", "ht": "height", "rt": "retention_time", "C": "concentration"}
"""calc value -> field of a terminus result."""

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ID_MAX_LENGTH = 64
COMMENT_MAX_LENGTH = 1024


def run_types_of(meta: pd.DataFrame) -> pd.Series:
    """The GCwerks run type of each run: ``type`` of the calc record, else the
    prefix of the run name (``std.123`` -> ``std``)."""
    names = meta["run"].astype(str).str.split(".").str[0]
    return meta["type"].where(meta["type"].astype(bool), names)


def terminus_id(name: str) -> str | None:
    """The terminus id of a GCwerks name (lower case), None if not a valid id."""
    value = str(name).strip().lower()
    return value if ID_RE.match(value) and len(value) <= ID_MAX_LENGTH else None


def compound_id(name: str) -> str | None:
    """An id for a new compound named ``name``: ``1,2-dichloroethane`` ->
    ``1-2-dichloroethane`` (like ``1-2-dichloropropane`` in peak.list),
    ``m+p-xylene`` -> ``m_p-xylene``."""
    value = str(name).strip().lower().replace(",", "-")
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = re.sub(r"^[_-]+", "", value)[:ID_MAX_LENGTH]
    return value or None


def float32_value(value: float) -> float:
    """The float32 ``value`` as the shortest decimal that gives it back: 530.12,
    not 530.1199951171875."""
    return float(str(np.float32(value)))


def utc_iso(time: pd.Timestamp) -> str:
    """A naive GMT timestamp as an ISO time with ``Z``."""
    return pd.Timestamp(time).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_tanks(calc: Calc, ports: pd.DataFrame | None = None) -> pd.Series:
    """The tank of each run: in the calc record, else on the run's port in the ports log.

    :return: Tank names, None where unknown, indexed like ``calc.meta``.
    """
    tanks = calc.meta["tank"].where(calc.meta["tank"] != "", None).astype(object)
    missing = tanks.isna()
    if missing.any() and ports is not None:
        on_ports = tanks_on_ports(
            ports, calc.meta.loc[missing, "time"], calc.meta.loc[missing, "port"]
        )
        tanks[missing] = on_ports.to_numpy()
    return tanks.where(tanks.notna(), None)


@dataclass
class Tank:
    """A tank (terminus sample) and what is known of it from the ports log."""

    name: str
    sample_id: str
    filled_at: pd.Timestamp
    description: str


def tank_info(name: str, ports: pd.DataFrame | None, first_run: pd.Timestamp) -> Tank:
    """The terminus sample of tank ``name``.

    ``filled_at`` is the fill date of the ports log, else the first time the
    tank was put on a port, else its first run.
    """
    sample_id = terminus_id(name)
    assert sample_id is not None
    lines = ports[ports["tank"] == name] if ports is not None else pd.DataFrame()
    fill_dates = lines["fill_date"].dropna() if not lines.empty else pd.Series(dtype=object)
    if not fill_dates.empty:
        filled_at = fill_dates.iloc[0]
    elif not lines.empty:
        filled_at = lines["time"].iloc[0]
    else:
        filled_at = first_run
    parts = [f"GCwerks tank {name}"]
    if not lines.empty:
        first = lines.iloc[0]
        if isinstance(first["regulator"], str):
            parts.append(f"regulator {first['regulator']}")
        if isinstance(first["comment"], str):
            parts.append(first["comment"])
    return Tank(name, sample_id, pd.Timestamp(filled_at), "; ".join(parts)[:1024])


@dataclass
class FlagSet:
    """GCwerks flags (letters and their comments) and their terminus bits."""

    entries: list[tuple[str, str | None]] = field(default_factory=list)

    def add(self, letter: str, comment: str | None = None) -> None:
        comment = comment if isinstance(comment, str) and comment else None  # NaN, ""
        if letter and (letter, comment) not in self.entries:
            self.entries.append((letter, comment))

    @property
    def letters(self) -> set[str]:
        return {letter for letter, _ in self.entries}

    def bits(self, unknown: set[str]) -> int:
        bits = Flag(0)
        for letter, _ in self.entries:
            if letter in GCWERKS_FLAGS:
                bits |= GCWERKS_FLAGS[letter]
            else:
                unknown.add(letter)
        if "X" in self.letters:  # validated by hand: undoes the "*" of GCwerks
            bits &= ~Flag.AUTO_REJECTED
        return int(bits)

    def comment(self) -> str | None:
        """``F: Gast; *``: each letter with its comments."""
        parts = []
        for letter in dict.fromkeys(letter for letter, _ in self.entries):
            comments = [c for le, c in self.entries if le == letter and c]
            if letter == "H" and not comments:
                continue  # height integration: the FROM_HEIGHT flag says it
            parts.append(f"{letter}: {' / '.join(comments)}" if comments else letter)
        text = "; ".join(parts)
        return text[:COMMENT_MAX_LENGTH] or None


@dataclass
class Conversion:
    """What the runs give: the measurements and what they need."""

    measurements: list[dict] = field(default_factory=list)
    tanks: dict[str, Tank] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    """Number of runs left out, by reason."""
    unknown_letters: set[str] = field(default_factory=set)
    """GCwerks flags without a terminus flag (ignored)."""

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def gases_with_values(calc: Calc, rows=None) -> list[str]:
    """The gases with at least one value (area, ht, rt or C) in the runs ``rows``."""
    values = calc.values if rows is None else calc.values[np.asarray(rows, dtype=bool)]
    columns = [(gas, variable) for gas in calc.gases for variable in VARIABLES]
    finite = np.isfinite(values[columns].to_numpy()).any(axis=0)
    return list(dict.fromkeys(gas for (gas, _), ok in zip(columns, finite, strict=True) if ok))


def convert(
    calc: Calc,
    instrument_id: str,
    compounds: dict[str, str],
    run_types: tuple[str, ...] = DEFAULT_RUN_TYPES,
    ports: pd.DataFrame | None = None,
    flags: pd.DataFrame | None = None,
) -> Conversion:
    """Build the measurements of the runs of ``calc``.

    :param calc: The runs (:func:`gcwerks.io.calc.read_calc`).
    :param instrument_id: The terminus instrument.
    :param compounds: GCwerks gas -> terminus compound id; other gases are
        left out.
    :param run_types: GCwerks run types to import.
    :param ports: The ports log, for the tank of runs without one and the
        fill dates.
    :param flags: The flag lines of the runs (:func:`gcwerks.io.flags.run_flags`
        on ``calc.meta``).
    """
    unknown = set(run_types) - set(RUN_TYPES)
    if unknown:
        raise ValueError(f"run types without a terminus type: {sorted(unknown)}")
    conversion = Conversion()
    meta = calc.meta
    tanks = run_tanks(calc, ports)
    lines: dict[int, list] = defaultdict(list)
    if flags is not None:
        for line in flags.itertuples(index=False):
            lines[line.run].append(line)

    gases = [gas for gas in calc.gases if gas in compounds]
    columns = pd.MultiIndex.from_product([gases, GAS_VALUES])
    values = calc.values[columns].to_numpy().reshape(len(meta), len(gases), len(GAS_VALUES))
    letters = calc.flags[pd.MultiIndex.from_product([gases, GAS_FLAGS])].to_numpy()
    letters = letters.reshape(len(meta), len(gases), len(GAS_FLAGS))
    value_index = {name: GAS_VALUES.index(name) for name in VARIABLES}
    flag_index = {name: GAS_FLAGS.index(name) for name in GAS_FLAGS}
    run_flag_columns = [c for c in ("flag1", "flag2", "flag3", "flag4") if c in meta]

    types = run_types_of(meta)
    seen: set[pd.Timestamp] = set()
    for row in range(len(meta)):
        run = meta.iloc[row]
        run_type = types.iloc[row]
        if run_type not in run_types:
            conversion.skip(f"run type {run_type}")
            continue
        time = run["time"]
        if time in seen:
            logger.warning(f"two runs at {time}, the second is skipped")
            conversion.skip("same time as another run")
            continue

        run_flags = FlagSet()
        for column in run_flag_columns:
            run_flags.add(run[column])
        gas_lines: dict[str, FlagSet] = defaultdict(FlagSet)
        for line in lines.get(row, []):
            target = run_flags if line.gas == ALL else gas_lines[line.gas]
            target.add(line.flag, line.comment)

        results = []
        for g, gas in enumerate(gases):
            result: dict = {"compound_id": compounds[gas]}
            for name, target in VARIABLES.items():
                value = values[row, g, value_index[name]]
                if math.isfinite(value):
                    result[target] = float32_value(value)
            if len(result) == 1:
                continue
            ht, area, flag, pollution = (letters[row, g, flag_index[n]] for n in GAS_FLAGS)
            gas_flags = FlagSet(list(gas_lines[gas].entries) if gas in gas_lines else [])
            # the flag of the reported value; those set for the whole run stay on it
            for letter in {ht if flag == "H" else area, flag, pollution} - run_flags.letters:
                if letter not in gas_flags.letters:
                    gas_flags.add(letter)
            result["flags"] = gas_flags.bits(conversion.unknown_letters)
            result["flag_comment"] = gas_flags.comment()
            results.append(result)

        measurement = {
            "instrument_id": instrument_id,
            "type": RUN_TYPES[run_type],
            "measured_at": utc_iso(time),
            "sample_id": None,
            "description": f"GCwerks {run['run'] or run_type} run",
            "flags": run_flags.bits(conversion.unknown_letters),
            "flag_comment": run_flags.comment(),
            "results": results,
        }
        if run_type in SAMPLE_RUN_TYPES:
            tank = tanks[row]
            if tank is None:
                logger.warning(f"{run_type} run at {time}: tank unknown, skipped")
                conversion.skip("tank unknown")
                continue
            sample_id = terminus_id(tank)
            if sample_id is None:
                logger.warning(
                    f"{run_type} run at {time}: tank {tank!r} is not a valid id, skipped"
                )
                conversion.skip("invalid tank name")
                continue
            if tank not in conversion.tanks:
                conversion.tanks[tank] = tank_info(tank, ports, time)
            measurement["sample_id"] = sample_id
            measurement["description"] = f"GCwerks {run['run'] or run_type} run of {tank}"
        seen.add(time)  # only once imported: a skipped run does not hide another
        conversion.measurements.append(measurement)
    return conversion
