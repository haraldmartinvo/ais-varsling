#!/usr/bin/env python3
"""
AIS-varsling: overvåker fartøy mot lokaliteter via BarentsWatch Live AIS API.

Kjøres periodisk av GitHub Actions. Holder tilstand i state.json.
Varsling skjer ved å opprette en GitHub-issue i repoet – GitHub sender da
automatisk e-post til deg (ingen SMTP eller egen e-postkonto nødvendig).

Miljøvariabler:
  BW_CLIENT_ID       BarentsWatch klient-ID (GitHub Secret)
  BW_CLIENT_SECRET   BarentsWatch klienthemmelighet (GitHub Secret)
  GITHUB_TOKEN       Settes automatisk av GitHub Actions
  GITHUB_REPOSITORY  Settes automatisk av GitHub Actions (eier/repo)
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

BASEDIR = Path(__file__).parent
STATE_FILE = BASEDIR / "state.json"
CONFIG_FILE = BASEDIR / "config.yaml"

TOKEN_URL = "https://id.barentswatch.no/connect/token"
LATEST_URL = "https://live.ais.barentswatch.no/v1/latest/combined"


def hent_token(client_id: str, client_secret: str) -> str:
    r = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "ais",
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def hent_posisjoner(token: str, mmsi_liste: list[int]) -> list[dict]:
    r = requests.post(
        LATEST_URL,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={"mmsi": mmsi_liste},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Avstand i meter mellom to koordinater."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def vurder_overgang(var_inne: bool, avstand_m: float, radius_m: float,
                    hysterese: float) -> tuple[bool, str | None]:
    """Returnerer (er_inne_nå, hendelse) der hendelse er 'ankomst', 'avgang' eller None."""
    if not var_inne and avstand_m <= radius_m:
        return True, "ankomst"
    if var_inne and avstand_m > radius_m * hysterese:
        return False, "avgang"
    return var_inne, None


def send_varsel(tittel: str, tekst: str) -> None:
    """Oppretter en GitHub-issue. GitHub e-poster deg automatisk om nye issues
    i ditt eget repo (forutsatt at du 'Watcher' repoet, som er standard)."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        # Kjøres lokalt uten GitHub – skriv bare til konsollen
        print(f"[VARSEL] {tittel}\n{tekst}\n")
        return
    r = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": tittel, "body": tekst, "labels": ["ais-varsel"]},
        timeout=30,
    )
    r.raise_for_status()
    print(f"Varsel opprettet: {r.json().get('html_url')}")


def maps_lenke(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q={lat},{lon}"


def main() -> int:
    config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    fartoy = {int(f["mmsi"]): f["navn"] for f in config["fartoy"]}
    lokaliteter = config["lokaliteter"]
    hysterese = float(config.get("hysterese", 1.5))
    stille_timer = float(config.get("stille_varsel_timer", 0) or 0)

    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    token = hent_token(os.environ["BW_CLIENT_ID"], os.environ["BW_CLIENT_SECRET"])
    posisjoner = hent_posisjoner(token, list(fartoy.keys()))
    naa = datetime.now(timezone.utc)

    rapportert = set()
    hendelser = []

    for pos in posisjoner:
        mmsi = int(pos["mmsi"])
        if mmsi not in fartoy:
            continue
        rapportert.add(mmsi)
        navn = pos.get("name") or fartoy[mmsi]
        lat, lon = pos["latitude"], pos["longitude"]
        fart = pos.get("speedOverGround")
        msgtime = pos.get("msgtime", "")

        vstate = state.setdefault(str(mmsi), {})
        vstate["sist_sett"] = naa.isoformat()
        vstate["sist_posisjon"] = {"lat": lat, "lon": lon, "msgtime": msgtime}
        vstate.pop("stille_varslet", None)

        for lok in lokaliteter:
            nokkel = f"lok_{lok['nr']}"
            var_inne = vstate.get(nokkel, {}).get("inne", False)
            avstand = haversine_m(lat, lon, lok["lat"], lok["lon"])
            inne, hendelse = vurder_overgang(var_inne, avstand,
                                             float(lok["radius_m"]), hysterese)
            vstate[nokkel] = {"inne": inne, "oppdatert": naa.isoformat()}

            if hendelse:
                verb = "ANKOMMET" if hendelse == "ankomst" else "DRATT FRA"
                tittel = f"⚓ {navn} har {verb} {lok['navn']} ({lok['nr']})"
                tekst = (
                    f"**Fartøy:** {navn} (MMSI {mmsi})\n"
                    f"**Hendelse:** {hendelse.upper()} – {lok['navn']} "
                    f"(lokalitet {lok['nr']})\n"
                    f"**Tidspunkt:** {msgtime}\n"
                    f"**Avstand til lokalitet:** {avstand:.0f} m\n"
                    f"**Fart:** {fart if fart is not None else 'ukjent'} knop\n"
                    f"**Posisjon:** {lat:.5f}, {lon:.5f}\n"
                    f"**Kart:** {maps_lenke(lat, lon)}\n\n"
                    f"_Automatisk varsel fra AIS-overvåking (BarentsWatch)_"
                )
                hendelser.append((tittel, tekst))
                print(f"HENDELSE: {tittel}")

    # Fartøy uten AIS-data (utenfor dekning eller sender ikke)
    for mmsi, navn in fartoy.items():
        if mmsi in rapportert:
            continue
        vstate = state.setdefault(str(mmsi), {})
        sist = vstate.get("sist_sett")
        print(f"MERK: Ingen AIS-data for {navn} (MMSI {mmsi}). Sist sett: {sist or 'aldri'}")
        if stille_timer > 0 and sist and not vstate.get("stille_varslet"):
            timer_siden = (naa - datetime.fromisoformat(sist)).total_seconds() / 3600
            if timer_siden > stille_timer:
                hendelser.append((
                    f"⚠️ {navn} har ikke sendt AIS-posisjon på {timer_siden:.0f} timer",
                    f"Fartøyet {navn} (MMSI {mmsi}) har ikke rapportert posisjon "
                    f"siden {sist}.\nDet kan være utenfor dekningsområdet eller ha "
                    f"slått av AIS-senderen.",
                ))
                vstate["stille_varslet"] = True

    for tittel, tekst in hendelser:
        send_varsel(tittel, tekst)

    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"OK – {len(posisjoner)} posisjon(er) sjekket, "
          f"{len(hendelser)} hendelse(r), {naa.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
