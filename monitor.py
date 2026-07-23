#!/usr/bin/env python3
"""
AIS-varsling: overvåker fartøy mot lokaliteter via BarentsWatch Live AIS API.

Kjøres som langkjøring i GitHub Actions: jobben lever i RUN_MINUTES minutter
og sjekker posisjoner hvert POLL_SECONDS sekund. Ved jobbslutt starter
workflowen sin egen etterfølger (se monitor.yml), slik at overvåkingen er
kontinuerlig uavhengig av GitHubs upålitelige cron-tidsplan.

Varsling: oppretter GitHub-issue -> GitHub sender e-post.

Miljøvariabler:
  BW_CLIENT_ID       BarentsWatch klient-ID (GitHub Secret)
  BW_CLIENT_SECRET   BarentsWatch klienthemmelighet (GitHub Secret)
  GITHUB_TOKEN       Settes automatisk av GitHub Actions
  GITHUB_REPOSITORY  Settes automatisk av GitHub Actions
  RUN_MINUTES        Hvor lenge jobben skal leve (0 = én enkelt sjekk)
  POLL_SECONDS       Sekunder mellom hver sjekk (standard 120)
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

BASEDIR = Path(__file__).parent
STATE_FILE = BASEDIR / "state.json"
CONFIG_FILE = BASEDIR / "config.yaml"

TOKEN_URL = "https://id.barentswatch.no/connect/token"
LATEST_URL = "https://live.ais.barentswatch.no/v1/latest/combined"

_token_cache = {"token": None, "utloper": 0.0}


def hent_token(client_id: str, client_secret: str) -> str:
    """Henter (og gjenbruker) OAuth-token. Fornyes når < 2 min gjenstår."""
    if _token_cache["token"] and time.time() < _token_cache["utloper"] - 120:
        return _token_cache["token"]
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
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["utloper"] = time.time() + float(data.get("expires_in", 3600))
    return _token_cache["token"]


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
                    hysterese: float, fart_knop: float | None = None,
                    maks_fart_knop: float = 0.0) -> tuple[bool, str | None]:
    """Returnerer (er_inne_nå, hendelse) der hendelse er 'ankomst', 'avgang' eller None.

    Med maks_fart_knop > 0 regnes fartøyet først som "på lokaliteten" når det
    er innenfor radius OG holder lav fart (<= maks_fart_knop). Fartøy som bare
    seiler forbi i marsjfart utløser dermed ingen varsler. Manglende fartsdata
    (None) tolkes som stilleliggende. Avgang krever kun at fartøyet forlater
    området geografisk – farten på vei ut spiller ingen rolle."""
    if not var_inne and avstand_m <= radius_m:
        if maks_fart_knop > 0 and fart_knop is not None and fart_knop > maks_fart_knop:
            return False, None   # bare på gjennomfart
        return True, "ankomst"
    if var_inne and avstand_m > radius_m * hysterese:
        return False, "avgang"
    return var_inne, None


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def send_varsel(tittel: str, tekst: str) -> None:
    """Oppretter GitHub-issue (-> e-post). Hopper over hvis en åpen issue
    allerede har identisk tittel (beskytter mot dubletter etter omstart)."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print(f"[VARSEL] {tittel}\n{tekst}\n")
        return
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers=_gh_headers(),
            params={"state": "open", "labels": "ais-varsel", "per_page": 20},
            timeout=30,
        )
        if r.ok and any(i["title"] == tittel for i in r.json()):
            print(f"Hopper over dublett: {tittel}")
            return
    except requests.RequestException:
        pass
    r = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers=_gh_headers(),
        json={"title": tittel, "body": tekst, "labels": ["ais-varsel"]},
        timeout=30,
    )
    r.raise_for_status()
    print(f"Varsel opprettet: {r.json().get('html_url')}")


def maps_lenke(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q={lat},{lon}"


def marinetraffic_lenke(mmsi: int) -> str:
    return f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{mmsi}"


def sjekk(config: dict, state: dict) -> int:
    """Én sjekkerunde. Returnerer antall hendelser."""
    fartoy = {int(f["mmsi"]): f["navn"] for f in config["fartoy"]}
    lokaliteter = config["lokaliteter"]
    hysterese = float(config.get("hysterese", 1.5))
    maks_fart = float(config.get("maks_fart_knop", 0) or 0)
    stille_timer = float(config.get("stille_varsel_timer", 0) or 0)

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
            lok_maks_fart = float(lok.get("maks_fart_knop", maks_fart) or 0)
            inne, hendelse = vurder_overgang(var_inne, avstand,
                                             float(lok["radius_m"]), hysterese,
                                             fart, lok_maks_fart)
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
                    f"**Kart:** {maps_lenke(lat, lon)}\n"
                    f"**MarineTraffic (live):** {marinetraffic_lenke(mmsi)}\n\n"
                    f"_Automatisk varsel fra AIS-overvåking (BarentsWatch)_"
                )
                hendelser.append((tittel, tekst))
                print(f"HENDELSE: {tittel}")

    for mmsi, navn in fartoy.items():
        if mmsi in rapportert:
            continue
        vstate = state.setdefault(str(mmsi), {})
        sist = vstate.get("sist_sett")
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
    print(f"[{naa.strftime('%H:%M:%S')}] {len(posisjoner)} posisjon(er) sjekket, "
          f"{len(hendelser)} hendelse(r)", flush=True)
    return len(hendelser)


def main() -> int:
    run_minutes = float(os.environ.get("RUN_MINUTES", "0") or 0)
    poll_seconds = float(os.environ.get("POLL_SECONDS", "120") or 120)

    config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    if run_minutes <= 0:
        sjekk(config, state)
        return 0

    slutt = time.time() + run_minutes * 60
    print(f"Langkjøring: {run_minutes:.0f} min, sjekk hvert {poll_seconds:.0f} s")
    while time.time() < slutt:
        try:
            sjekk(config, state)
        except Exception as e:
            # Ikke dø på forbigående API-feil; prøv igjen neste runde
            print(f"ADVARSEL: {type(e).__name__}: {e}", flush=True)
        gjenstaar = slutt - time.time()
        if gjenstaar <= 0:
            break
        time.sleep(min(poll_seconds, gjenstaar))
    print("Langkjøring ferdig – etterfølger startes av workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
