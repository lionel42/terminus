"""A small GCwerks directory: peak.list, a calc file, flags and the ports log."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from gcwerks.io.calc import GAS_FLAGS, GAS_VALUES, write_calc

GASES = ["CFC-12", "N2O", "m+p-xylene"]
RUNS = pd.DataFrame(
    {
        "time": pd.to_datetime(
            [
                "2025-01-01 00:13",  # std E-223
                "2025-01-01 01:23",  # air
                "2025-01-02 00:13",  # tert J-290, flagged as a whole
                "2025-01-20 11:00",  # tank, no tank in the record: port 1 in the ports log
                "2025-01-21 12:00",  # std E-223
            ]
        ),
        "run": ["std.5", "air.7", "tert.11", "tank.1", "std.5"],
        "type": ["std", "air", "tert", "tank", "std"],
        "port": [5, 7, 11, 1, 5],
        "tank": ["E-223", "2m_air", "J-290", "", "E-223"],
    }
)


def _value(name: str) -> int:
    return GAS_VALUES.index(name)


def _flag(name: str) -> int:
    return GAS_FLAGS.index(name)


def write_gcdir(root: Path) -> Path:
    (root / "config").mkdir(parents=True)
    (root / "config" / "peak.list").write_text("\n".join(GASES) + "\n#HFC-999\n")
    values = np.full((len(RUNS), len(GASES), len(GAS_VALUES)), np.nan)
    for run in range(len(RUNS)):
        values[run, 0, [_value("rt"), _value("ht"), _value("area")]] = [410.5, 1800.5, 150000]
        values[run, 0, _value("C")] = 530.12
        values[run, 1, _value("area")] = 2000 + run
    values[4, 2, _value("ht")] = 50.0  # m+p-xylene: only in the last run
    flags = np.full((len(RUNS), len(GASES), len(GAS_FLAGS)), "")
    flags[0, 1, _flag("flag_a")] = "*"  # N2O of the first std: rejected by GCwerks
    flags[0, 1, _flag("flag_ht")] = "B"  # by height: not reported, ignored
    flags[2, :, _flag("flag_a")] = "F"  # the whole tert run (from data/flags "all")
    flags[3, 0, _flag("flag_a")] = "F"  # CFC-12 of the tank run (data/flags-range)
    flags[4, 2, _flag("flag")] = "H"  # m+p-xylene by height
    calc_dir = root / "results" / "calc"
    calc_dir.mkdir(parents=True)
    write_calc(calc_dir / "calc.2025", RUNS, values, flags)

    (root / "data" / "flags").mkdir(parents=True)
    (root / "data" / "flags" / "2501").write_text(
        "250102 0013  all     F  valve not turned\n250101 0013  N2O  X\n"
    )
    (root / "data" / "flags-range").mkdir()
    (root / "data" / "flags-range" / "2025").write_text(
        "250120 0000  250120 2359  tank  CFC-12  F  # contaminated\n"
    )
    (root / "logs" / "ports.log").mkdir(parents=True)
    (root / "logs" / "ports.log" / "0701").write_text(
        "241122 1355 5 E-223 V-102544 std - 241101 # quat ESX-3414\n"
        "250120 1052 1 E-223-D2 noreg tank - 250115.1200 # filled to 3 bar\n"
    )
    return root


@pytest.fixture
def gcdir(tmp_path: Path) -> Path:
    return write_gcdir(tmp_path / "gcdir")
