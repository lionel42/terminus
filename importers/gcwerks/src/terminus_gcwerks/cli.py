"""``terminus-gcwerks``: import the runs of a GCwerks directory into terminus.

Examples::

    # the std, tert and tank runs since 2025
    terminus-gcwerks /agage/jungfraujoch-medusa --instrument jfj-medusa --from 2025-01-01

    # check everything, write nothing
    terminus-gcwerks /agage/jungfraujoch-medusa --instrument jfj-medusa --dry-run -v

It reads the GCwerks files directly: ``results/calc/calc.<yyyy>`` (the
results of each run), ``config/peak.list`` (the gases), ``data/flags`` and
``data/flags-range`` (the flags and their comments) and ``logs/ports.log``
(the tanks). The server and the account come from ``TERMINUS_URL`` and
``TERMINUS_TOKEN``, or ``TERMINUS_EMAIL`` and ``TERMINUS_PASSWORD`` (a superuser).
"""

import argparse
import logging
import os
import re
import sys
from collections import Counter
from datetime import date

import httpx
import pandas as pd
from gcwerks.io.calc import read_calc_years
from gcwerks.io.flags import ALL, read_flags, read_range_flags, run_flags
from gcwerks.io.peaks import read_peak_list
from gcwerks.io.ports import read_ports_log
from gcwerks.paths import GCWerksPaths

from terminus_gcwerks.client import TerminusClient, TerminusError
from terminus_gcwerks.convert import (
    DEFAULT_RUN_TYPES,
    RUN_TYPES,
    Flag,
    compound_id,
    convert,
    gases_with_values,
    run_types_of,
    utc_iso,
)

logger = logging.getLogger("terminus_gcwerks")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminus-gcwerks",
        description="Import the runs of a GCwerks directory into terminus.",
    )
    parser.add_argument("gcdir", help="the GCwerks directory")
    parser.add_argument("--instrument", required=True, help="terminus instrument id")
    parser.add_argument(
        "--from", dest="start", type=date.fromisoformat, help="first day, YYYY-MM-DD"
    )
    parser.add_argument("--to", dest="end", type=date.fromisoformat, help="last day, YYYY-MM-DD")
    parser.add_argument(
        "--gas", action="append", dest="gases", help="import only this gas (repeat)"
    )
    parser.add_argument(
        "--types",
        default=",".join(DEFAULT_RUN_TYPES),
        help=f"GCwerks run types to import, comma-separated (default: %(default)s;"
        f" known: {', '.join(RUN_TYPES)})",
    )
    parser.add_argument(
        "--mode",
        choices=["skip", "replace"],
        default="skip",
        help="runs already in terminus: keep them (skip) or overwrite their values"
        " (replace; the flags in terminus are kept, the imported ones added)",
    )
    parser.add_argument(
        "--no-new-compounds",
        action="store_true",
        help="leave out the gases that are no terminus compound, instead of registering them",
    )
    parser.add_argument("--url", default=os.environ.get("TERMINUS_URL"), help="terminus server")
    parser.add_argument("--batch-size", type=int, default=200, help="measurements per request")
    parser.add_argument(
        "--dry-run", action="store_true", help="check everything, write nothing to terminus"
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    if not args.url:
        parser.error("set --url or TERMINUS_URL")
    if args.start and args.end and args.start > args.end:
        parser.error("--from is after --to")
    return args


def connect(url: str) -> TerminusClient:
    client = TerminusClient(url, token=os.environ.get("TERMINUS_TOKEN"))
    if "TERMINUS_TOKEN" not in os.environ:
        email, password = os.environ.get("TERMINUS_EMAIL"), os.environ.get("TERMINUS_PASSWORD")
        if not (email and password):
            raise TerminusError("set TERMINUS_TOKEN, or TERMINUS_EMAIL and TERMINUS_PASSWORD")
        client.login(email, password)
    return client


def check_flags(client: TerminusClient) -> None:
    """The server must have the flags this importer maps to."""
    server = client.flags()
    wrong = [f.name for f in Flag if server.get(f.name) != int(f)]
    if wrong:
        raise TerminusError(
            f"the server's quality flags differ from the importer's: {', '.join(wrong)}"
            " (update terminus or the importer)"
        )


def years(paths: GCWerksPaths, start: date | None, end: date | None) -> list[int]:
    found = sorted(
        int(p.name[5:])
        for p in paths.calc_dir.glob("calc.*")
        if re.fullmatch(r"calc\.\d{4}", p.name)
    )
    return [y for y in found if (not start or y >= start.year) and (not end or y <= end.year)]


def resolve_compounds(
    client: TerminusClient, gases: list[str], args: argparse.Namespace, origin: str
) -> tuple[dict[str, str], list[str], list[str]]:
    """GCwerks gas -> compound id, registering the missing compounds.

    :return: The compounds, the gases registered (or to register on a dry
        run) and the gases left out.
    """
    compounds, created, left_out = {}, [], []
    new_ids: dict[str, str] = {}  # registered here: id -> gas
    for gas in gases:
        found = client.resolve_compound(gas)
        if found is not None:
            compounds[gas] = found
            continue
        new_id = compound_id(gas)
        if args.no_new_compounds or new_id is None:
            left_out.append(gas)
            continue
        if new_id in new_ids:
            logger.warning(
                f"gas {gas}: its compound id {new_id!r} is the one of gas"
                f" {new_ids[new_id]!r}, registered just before. Left out."
            )
            left_out.append(gas)
            continue
        if client.get(f"/compounds/{new_id}") is not None:
            logger.warning(
                f"gas {gas}: the compound {new_id!r} exists but is not named {gas!r};"
                f" add {gas!r} as one of its aliases if it is the same. Left out."
            )
            left_out.append(gas)
            continue
        if not args.dry_run:
            client.create_compound(
                gas, new_id, f"Registered from the GCwerks peak.list of {origin}"
            )
        compounds[gas] = new_id
        new_ids[new_id] = gas
        created.append(gas)
    return compounds, created, left_out


def run(args: argparse.Namespace, client: TerminusClient) -> int:
    paths = GCWerksPaths(args.gcdir)
    if not paths.root.is_dir():
        raise FileNotFoundError(f"GCwerks directory not found: {paths.root}")
    run_types = tuple(t.strip() for t in args.types.split(",") if t.strip())
    if client.get(f"/instruments/{args.instrument}") is None:
        raise TerminusError(f"instrument {args.instrument!r} not found in terminus")
    check_flags(client)

    peak_list = read_peak_list(paths.peak_list)["name"].tolist()
    selected_years = years(paths, args.start, args.end)
    if not selected_years:
        raise FileNotFoundError(f"no results file in {paths.calc_dir} for these dates")
    calc = read_calc_years(paths.calc_dir, selected_years, peak_list)
    times = calc.meta["time"]
    keep = run_types_of(calc.meta).isin(run_types).to_numpy().copy()
    if args.start:
        keep &= (times >= pd.Timestamp(args.start)).to_numpy()
    if args.end:
        keep &= (times < pd.Timestamp(args.end) + pd.Timedelta(days=1)).to_numpy()
    calc = calc.select(keep)
    logger.info(f"{len(calc.meta)} runs in calc.{selected_years[0]}..{selected_years[-1]}")

    gases = gases_with_values(calc)
    if args.gases:
        unknown = sorted(set(args.gases) - set(calc.gases))
        if unknown:
            raise ValueError(f"gases not in peak.list: {', '.join(unknown)}")
        gases = [gas for gas in gases if gas in args.gases]
    repeated = [gas for gas in gases if "~" in gas]
    if repeated:
        logger.warning(f"gases listed twice in peak.list, the second is left out: {repeated}")
        gases = [gas for gas in gases if gas not in repeated]
    compounds, created, left_out = resolve_compounds(client, gases, args, paths.root.name)
    if created:
        logger.warning(
            f"{len(created)} gases registered as new compounds"
            f"{' (dry run: not done)' if args.dry_run else ''}: {', '.join(created)}"
        )
    if left_out:
        logger.warning(f"{len(left_out)} gases left out: {', '.join(left_out)}")

    ports = read_ports_log(paths.ports_log) if paths.ports_log.exists() else None
    flag_lines = run_flags(
        calc.meta["time"],
        calc.meta["type"],
        calc.meta["port"],
        read_flags(paths.flags) if paths.flags.exists() else None,
        read_range_flags(paths.range_flags) if paths.range_flags.exists() else None,
    )
    not_gases = sorted(set(flag_lines["gas"]) - set(calc.gases) - {ALL})
    if not_gases:
        logger.warning(f"flags of gases not in peak.list, ignored: {', '.join(not_gases)}")

    conversion = convert(calc, args.instrument, compounds, run_types, ports, flag_lines)
    for reason, n in sorted(conversion.skipped.items()):
        logger.info(f"{n} runs skipped: {reason}")
    if conversion.unknown_letters:
        logger.warning(
            f"GCwerks flags without a terminus flag, ignored: {sorted(conversion.unknown_letters)}"
        )

    samples = Counter()
    for tank in conversion.tanks.values():
        status = client.ensure_sample(
            tank.sample_id, utc_iso(tank.filled_at), tank.description, dry_run=args.dry_run
        )
        samples[status] += 1
        if status != "exists":
            logger.info(f"sample {tank.sample_id} {status} (filled at {tank.filled_at})")

    measurements = conversion.measurements
    flagged = sum(1 for m in measurements if m["flags"])
    flagged_results = sum(1 for m in measurements for r in m["results"] if r["flags"])
    report = Counter()
    if args.dry_run:
        logger.info(f"dry run: {len(measurements)} measurements would be imported")
    else:
        for start in range(0, len(measurements), args.batch_size):
            batch = measurements[start : start + args.batch_size]
            report.update(client.import_measurements(batch, args.mode))
            logger.info(f"imported {start + len(batch)}/{len(measurements)}")
    print(
        f"measurements: {len(measurements)} ({dict(report) or 'dry run'}),"
        f" flagged: {flagged} runs and {flagged_results} results;"
        f" samples: {dict(samples)}; compounds registered: {len(created)};"
        f" gases left out: {len(left_out)}; skipped runs: {sum(conversion.skipped.values())}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2), format="%(levelname)s %(message)s"
    )
    # one line per request: only with -vv
    logging.getLogger("httpx").setLevel(logging.DEBUG if args.verbose > 1 else logging.WARNING)
    try:
        with connect(args.url) as client:
            return run(args, client)
    except (TerminusError, ValueError, FileNotFoundError) as error:
        logger.error(error)
        return 1
    except httpx.HTTPError as error:
        logger.error(f"terminus server {args.url}: {error!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
