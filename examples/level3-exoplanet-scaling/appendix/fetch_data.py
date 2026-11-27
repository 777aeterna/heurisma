#!/usr/bin/env python3
"""Fetch confirmed transiting exoplanet data (primary + uncertainty/transit-ratio extension) from NASA Exoplanet Archive TAP API."""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

APPENDIX = Path(__file__).resolve().parent
if str(APPENDIX) not in sys.path:
    sys.path.insert(0, str(APPENDIX))

from fetch_lib import fetch  # noqa: E402

TAP_BASE = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
ADQL_QUERY = (
    "select pl_name,hostname,discoverymethod,disc_year,tran_flag,"
    "pl_orbper,pl_orbsmax,st_mass,pl_bmasse,pl_bmassprov,pl_rade,pl_orbeccen "
    "from ps "
    "where default_flag=1 and tran_flag=1 "
    "and pl_orbper is not null and pl_orbsmax is not null "
    "and st_mass between 0.1 and 2.5 "
    "and pl_bmasse is not null and pl_rade is not null "
    "order by pl_orbper asc"
)

ADQL_EXT_QUERY = (
    "select pl_name,pl_ratdor,st_rad,"
    "pl_orbsmaxerr1,pl_orbsmaxerr2,st_masserr1,st_masserr2,"
    "pl_bmasseerr1,pl_bmasseerr2,pl_radeerr1,pl_radeerr2 "
    "from ps "
    "where default_flag=1 and tran_flag=1 "
    "and pl_orbper is not null and pl_orbsmax is not null "
    "and st_mass between 0.1 and 2.5 "
    "and pl_bmasse is not null and pl_rade is not null "
    "order by pl_orbper asc"
)


def main() -> int:
    url = f"{TAP_BASE}?{urllib.parse.urlencode({'query': ADQL_QUERY, 'format': 'csv'})}"
    out_path = fetch(
        target="Confirmed Transiting Exoplanets (NASA Exoplanet Archive PS)",
        source="NASA Exoplanet Archive TAP API",
        url=url,
        filename="exoplanets_nasa_ps.csv",
        appendix=APPENDIX,
        allow_private=False,
        timeout=60,
    )
    if out_path is None:
        print("Failed to fetch NASA Exoplanet Archive data; see appendix/data_attempts.csv", file=sys.stderr)
        return 1
    print(f"Downloaded: {out_path}")

    url_ext = f"{TAP_BASE}?{urllib.parse.urlencode({'query': ADQL_EXT_QUERY, 'format': 'csv'})}"
    out_ext = fetch(
        target="Confirmed Transiting Exoplanets Uncertainties & Transit a/R_* (NASA Exoplanet Archive PS)",
        source="NASA Exoplanet Archive TAP API",
        url=url_ext,
        filename="exoplanets_nasa_ps_ext.csv",
        appendix=APPENDIX,
        allow_private=False,
        timeout=60,
    )
    if out_ext is None:
        print("Failed to fetch NASA Exoplanet Archive extended columns; see appendix/data_attempts.csv", file=sys.stderr)
        return 1
    print(f"Downloaded: {out_ext}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
