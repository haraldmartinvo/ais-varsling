#!/usr/bin/env python3
"""
Slå opp liveposisjon for fartøy via BarentsWatch Live AIS API.

Bruk:
  python posisjon.py GROTANGER          # navn fra config.yaml
  python posisjon.py 257699000          # eller MMSI direkte

Krever miljøvariablene BW_CLIENT_ID og BW_CLIENT_SECRET
(kan også legges i en .env-fil i samme mappe).
"""

import os
import sys
from pathlib import Path

import yaml

from monitor import hent_token, hent_posisjoner, maps_lenke, haversine_m

BASEDIR = Path(__file__).parent


def last_env_fil():
    env = BASEDIR / ".env"
    if env.exists():
        for linje in env.read_text().splitlines():
            if "=" in linje and not linje.strip().startswith("#"):
                k, v = linje.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    last_env_fil()
    config = yaml.safe_load((BASEDIR / "config.yaml").read_text(encoding="utf-8"))

    if len(sys.argv) < 2:
        print("Bruk: python posisjon.py <navn eller MMSI>")
        return 1

    arg = sys.argv[1].upper()
    if arg.isdigit():
        mmsi = int(arg)
    else:
        treff = [f for f in config["fartoy"] if f["navn"].upper() == arg]
        if not treff:
            print(f"Fant ikke '{arg}' i config.yaml. Oppgi MMSI direkte.")
            return 1
        mmsi = int(treff[0]["mmsi"])

    token = hent_token(os.environ["BW_CLIENT_ID"], os.environ["BW_CLIENT_SECRET"])
    posisjoner = hent_posisjoner(token, [mmsi])

    if not posisjoner:
        print(f"Ingen AIS-data for MMSI {mmsi} (utenfor dekning, eller ingen "
              f"posisjon siste døgn).")
        return 1

    p = posisjoner[0]
    lat, lon = p["latitude"], p["longitude"]
    print(f"Fartøy:   {p.get('name', mmsi)} (MMSI {mmsi})")
    print(f"Tid:      {p.get('msgtime')}")
    print(f"Posisjon: {lat:.5f}, {lon:.5f}")
    print(f"Fart:     {p.get('speedOverGround')} knop, kurs {p.get('courseOverGround')}°")
    print(f"Kart:     {maps_lenke(lat, lon)}")

    for lok in config.get("lokaliteter", []):
        d = haversine_m(lat, lon, lok["lat"], lok["lon"])
        enhet = f"{d/1852:.1f} nm" if d > 5000 else f"{d:.0f} m"
        print(f"Avstand til {lok['navn']} ({lok['nr']}): {enhet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
