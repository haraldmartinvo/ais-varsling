# AIS-varsling for lokaliteter

Overvåker fartøy (f.eks. brønnbåter) mot dine lokaliteter via BarentsWatch
Live AIS API. Kjører gratis på GitHub Actions hvert 10. minutt – ingen egen
server, ingen e-postkonto og ingen SMTP-oppsett nødvendig.

**Varsling:** når et fartøy ankommer/drar, opprettes en «issue» i GitHub-repoet
ditt – og GitHub sender deg automatisk e-post om den (vanlig innkommende
e-post fra github.com, går gjennom alle brannmurer).

Ferdig konfigurert: **MS Grotanger** (MMSI 257699000) mot
**lokalitet 11363 Enkeltstein** (68.727583°N, 16.910167°Ø).

---

## Oppsett (én gang)

### 1. BarentsWatch API-tilgang (gratis)

1. Registrer bruker på <https://www.barentswatch.no/minside/>
2. Min side → **API-klienter** → opprett ny klient av typen **AIS-klient**
3. Noter **client ID** (ser ut som `dinepost@domene.no:klientnavn`) og **client secret**

### 2. GitHub-repo

1. Opprett konto på <https://github.com> – **bruk hm@enkeltstein.no som
   e-post**, det er dit varslene sendes
2. Opprett nytt repository, f.eks. `ais-varsling` (offentlig = ubegrenset
   gratis kjøring; privat går også fint med cron `*/30`)
3. Last opp alle filene i denne mappen (behold mappestrukturen
   `.github/workflows/monitor.yml`)

### 3. To hemmeligheter

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Navn             | Verdi                              |
|------------------|-------------------------------------|
| BW_CLIENT_ID     | Klient-ID fra BarentsWatch          |
| BW_CLIENT_SECRET | Klienthemmelighet fra BarentsWatch  |

Det er alt – ingen e-postinnstillinger.

### 4. Aktiver og test

1. Fanen **Actions** → godta at workflows aktiveres
2. «AIS-overvaking» → **Run workflow** for manuell testkjøring
3. Loggen skal vise `OK – 1 posisjon(er) sjekket ...`

**Sjekk varslingsinnstillinger:** øverst i repoet, knappen **Watch** skal stå
på «All activity» (standard for egne repo). I GitHub-profilen:
Settings → Notifications → huk av **Email** for Participating/Watching.

---

## Daglig bruk

### Legge til fartøy eller lokaliteter

Rediger `config.yaml` rett i nettleseren på github.com:

```yaml
fartoy:
  - navn: GROTANGER
    mmsi: 257699000
  - navn: RONJA POLARIS
    mmsi: 257999999      # finn MMSI på vesselfinder.com / marinetraffic.com

lokaliteter:
  - navn: Enkeltstein
    nr: 11363
    lat: 68.727583
    lon: 16.910167
    radius_m: 800
```

Koordinater til enhver lokalitet (også slakterier) hentes åpent hos
Fiskeridirektoratet: `https://api.fiskeridir.no/pub-aqua/api/v1/sites/<lokalitetsnr>`
(feltene `latitude`/`longitude`).

### Slå opp liveposisjon

Lokalt på egen PC (krever Python og en `.env`-fil med BW_CLIENT_ID og
BW_CLIENT_SECRET):

```
pip install -r requirements.txt
python posisjon.py GROTANGER
```

Gir posisjon, fart, kartlenke og avstand til dine lokaliteter.

### Justeringer

- `radius_m`: hvor nær lokaliteten fartøyet må være for «ankomst»
- `stille_varsel_timer`: f.eks. `6` for varsel hvis fartøyet slutter å sende AIS
- Sjekkfrekvens: cron-linjen i `.github/workflows/monitor.yml`
- Gamle varsel-issues kan lukkes når som helst – de påvirker ingenting

---

## Begrensninger verdt å vite

- Åpne AIS-data dekker norsk økonomisk sone (+ Svalbard/Jan Mayen)
- GitHub Actions cron kan forsinkes 5–15 min i travle perioder
- API-et gir ikke historikk eldre enn 14 dager

## Videre utbygging

- Områdekryssing/karantene: logge fartøy som bytter produksjonsområde og
  flagge for kort tid mellom (brakklegging/karantene)
- Daglig oppsummering, kart-dashbord med spor siste 24 t
