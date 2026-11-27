import numpy as np
import pandas as pd
import pytest
from conftest import GASES
from gcwerks.io.calc import read_calc
from gcwerks.io.flags import read_flags, read_range_flags, run_flags
from gcwerks.io.ports import read_ports_log
from gcwerks.paths import GCWerksPaths

from terminus_gcwerks.convert import (
    Flag,
    FlagSet,
    compound_id,
    convert,
    float32_value,
    gases_with_values,
    run_tanks,
    run_types_of,
    tank_info,
    terminus_id,
)

COMPOUNDS = {"CFC-12": "cfc12", "N2O": "n2o", "m+p-xylene": "m_p-xylene"}


@pytest.fixture
def data(gcdir):
    paths = GCWerksPaths(gcdir)
    calc = read_calc(paths.calc(2025), GASES)
    ports = read_ports_log(paths.ports_log)
    meta = calc.meta
    flags = run_flags(
        meta["time"], meta["type"], meta["port"], read_flags(paths.flags),
        read_range_flags(paths.range_flags),
    )  # fmt: skip
    return calc, ports, flags


def test_ids():
    assert terminus_id("E-223-D2") == "e-223-d2"
    assert terminus_id(" 14m_air ") == "14m_air"
    assert terminus_id("bad.name") is None
    assert terminus_id("-x") is None
    assert terminus_id("x" * 65) is None
    assert compound_id("m+p-xylene") == "m_p-xylene"
    assert compound_id("1,1-dichloroethene") == "1-1-dichloroethene"
    assert compound_id("CFC-12") == "cfc-12"
    assert compound_id("+-") is None


def test_flag_set():
    flags = FlagSet()
    flags.add("F", "Gast")
    flags.add("F", "Gast")  # once
    flags.add("F", float("nan"))
    flags.add("*")
    flags.add("H")
    flags.add("")
    unknown: set[str] = set()
    assert flags.bits(unknown) == Flag.INVALID | Flag.AUTO_REJECTED | Flag.FROM_HEIGHT
    assert flags.comment() == "F: Gast; *"  # a bare H is said by FROM_HEIGHT
    FlagSet([("Q", None)]).bits(unknown)
    assert unknown == {"Q"}
    # "X" validates by hand what GCwerks rejected with "*"
    assert FlagSet([("*", None), ("X", None)]).bits(unknown) == 0
    assert FlagSet([("*", None), ("X", None), ("F", None)]).bits(unknown) == Flag.INVALID


def test_float32_value():
    assert float32_value(np.float32(530.12)) == 530.12
    assert float32_value(np.float32(91.14497375488281)) == 91.14497


def test_run_tanks(data):
    calc, ports, _ = data
    # in the record, else on the run's port in the ports log
    assert run_tanks(calc, ports).tolist() == ["E-223", "2m_air", "J-290", "E-223-D2", "E-223"]
    assert run_tanks(calc).tolist()[3] is None


def test_tank_info(data):
    _, ports, _ = data
    first_run = pd.Timestamp("2025-03-01")
    d2 = tank_info("E-223-D2", ports, first_run)
    assert d2.sample_id == "e-223-d2"
    assert d2.filled_at == pd.Timestamp("2025-01-15 12:00")  # fill date
    assert d2.description == "GCwerks tank E-223-D2; regulator noreg; filled to 3 bar"
    j290 = tank_info("J-290", ports, first_run)  # not in the ports log: first run
    assert (j290.filled_at, j290.description) == (first_run, "GCwerks tank J-290")


def test_gases_with_values(data):
    calc, _, _ = data
    assert gases_with_values(calc) == GASES
    assert gases_with_values(calc, calc.meta["type"] == "air") == ["CFC-12", "N2O"]


def test_convert(data):
    calc, ports, flags = data
    conversion = convert(calc, "jfj-medusa", COMPOUNDS, ports=ports, flags=flags)
    assert conversion.skipped == {"run type air": 1}
    measurements = {m["measured_at"]: m for m in conversion.measurements}
    assert [m["sample_id"] for m in measurements.values()] == [
        "e-223",
        "j-290",
        "e-223-d2",
        "e-223",
    ]
    assert set(conversion.tanks) == {"E-223", "J-290", "E-223-D2"}

    std = measurements["2025-01-01T00:13:00Z"]
    assert (std["type"], std["flags"], std["flag_comment"]) == ("standard", 0, None)
    assert std["description"] == "GCwerks std.5 run of E-223"
    cfc12, n2o = std["results"]
    assert cfc12 == {
        "compound_id": "cfc12",
        "area": 150000.0,
        "height": 1800.5,
        "retention_time": 410.5,
        "concentration": 530.12,
        "flags": 0,
        "flag_comment": None,
    }
    # area reported: its "*" counts, the "B" of the height not; the "X" of
    # data/flags undoes the "*"
    assert (n2o["area"], n2o["flags"], n2o["flag_comment"]) == (2000.0, 0, "X; *")

    # "all" flag: on the measurement, not repeated on each result
    tert = measurements["2025-01-02T00:13:00Z"]
    assert (tert["type"], tert["flags"]) == ("tert", Flag.INVALID)
    assert tert["flag_comment"] == "F: valve not turned"
    assert [r["flags"] for r in tert["results"]] == [0, 0]

    # range flag of one gas, with its comment
    tank = measurements["2025-01-20T11:00:00Z"]
    assert tank["flags"] == 0
    assert tank["results"][0]["flags"] == Flag.INVALID
    assert tank["results"][0]["flag_comment"] == "F: contaminated"

    xylene = measurements["2025-01-21T12:00:00Z"]["results"][2]
    assert xylene == {
        "compound_id": "m_p-xylene",
        "height": 50.0,
        "flags": Flag.FROM_HEIGHT,
        "flag_comment": None,
    }


def test_convert_types(data):
    calc, ports, flags = data
    conversion = convert(calc, "i", COMPOUNDS, run_types=("air",), flags=flags)
    (air,) = conversion.measurements
    assert (air["type"], air["sample_id"], air["description"]) == ("air", None, "GCwerks air.7 run")
    # without the ports log, the tank run has no tank
    conversion = convert(calc, "i", COMPOUNDS, run_types=("tank",))
    assert conversion.measurements == []
    assert conversion.skipped["tank unknown"] == 1
    # only the compounds given
    conversion = convert(calc, "i", {"N2O": "n2o"}, ports=ports)
    assert {r["compound_id"] for m in conversion.measurements for r in m["results"]} == {"n2o"}
    with pytest.raises(ValueError, match="flask"):
        convert(calc, "i", COMPOUNDS, run_types=("flask",))


def test_run_type_from_name(data):
    calc, ports, flags = data
    calc.meta.loc[0, "type"] = ""  # std.5
    assert run_types_of(calc.meta).tolist() == ["std", "air", "tert", "tank", "std"]
    conversion = convert(calc, "i", COMPOUNDS, ports=ports, flags=flags)
    assert conversion.measurements[0]["type"] == "standard"


def test_skipped_run_does_not_hide_another(data):
    calc, ports, flags = data
    calc.meta.loc[0, "tank"] = "bad.name"  # the std run: skipped
    calc.meta.loc[1, "time"] = calc.meta.loc[0, "time"]  # the air run, same time
    conversion = convert(calc, "i", COMPOUNDS, run_types=("std", "air"), ports=ports)
    assert conversion.skipped["invalid tank name"] == 1
    assert "same time as another run" not in conversion.skipped
    assert [m["type"] for m in conversion.measurements] == ["air", "standard"]
