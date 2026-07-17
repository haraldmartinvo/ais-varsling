# AIS-varsling for lokaliteter

Overvåker fartøy (f.eks. brønnbåter) mot dine lokaliteter via BarentsWatch
Live AIS API, og sender e-post når fartøy ankommer eller drar. Kjører gratis
på GitHub Actions hvert 10. minutt – ingen egen server nødvendig.

Ferdig konfigurert: **MS Grotanger** (MMSI 257699000) mot
**lokalitet 11363 Enkeltstein** (68.727583°N, 16.910167°Ø).

---

## Oppsett (ca. 20 minutter, én gang)

### 1. BarentsWatch API-tilgang (gratis)

1. Registrer bruker på <https://www.barentswatch.no/minside/>
2. Logg inn på Min side → **API-klienter** → opprett ny klient av typen **AIS-klient**
3. Noter **client ID** (ser ut som `dinepost@domene.no:klientnavn`) og **client secret**

### 2. Legg prosjektet på GitHub

1. Opprett konto på <https://github.com> om du ikke har
2. Opprett nytt repository, f.eks. `ais-varsling`.
   **Tips:** Gjør det *offentlig* – da er Actions-kjøring ubegrenset gratis.
   (Hemmelighetene dine ligger trygt i Secrets uansett, og AIS-data er åpne.
   Vil du ha privat repo: gratis­kvoten er 2000 min/mnd – sett da cron til
   `*/30` i `.github/workflows/monitor.yml`.)
3. Last opp alle filene i denne mappen til repoet (dra-og-slipp på github.com
   fungerer – husk at `.github/workflows/monitor.yml` må beholde mappestrukturen)

### 3. Legg inn hemmeligheter

I repoet: **Settings → Secrets and variables → Actions → New repository secret**.
Opprett disse:

| Navn             | Verdi                                          |
|------------------|------------------------------------------------|
| BW_CLIENT_ID     | Klient-ID fra BarentsWatch                      |
| BW_CLIENT_SECRET | Klienthemmelighet fra BarentsWatch              |
| SMTP_HOST        | f.eks. `smtp.gmail.com`                         |
| SMTP_PORT        | `587`                                           |
| SMTP_USER        | e-postadressen som sender                       |
| SMTP_PASS        | passord / app-passord (se under)                |
| EPOST_FRA        | avsenderadresse (vanligvis samme som SMTP_USER) |

**Anbefalt e-postløsning – Gmail med app-passord:**
1. Opprett gjerne en egen Gmail-konto for varsling (f.eks. `enkeltstein.varsling@gmail.com`)
2. Slå på 2-trinnsverifisering på kontoen
3. Gå til <https://myaccount.google.com/apppasswords> og opprett et app-passord
4. Bruk dette som `SMTP_PASS`

Alternativ: bruk SMTP-innstillingene til e-postleverandøren for enkeltstein.no
(Domeneshop: `smtp.domeneshop.no`, port 587, vanlig brukernavn/passord).

### 4. Aktiver og test

1. I repoet: fanen **Actions** → godta at workflows aktiveres
2. Velg «AIS-overvaking» → **Run workflow** for en manuell testkjøring
3. Sjekk loggen – den skal vise `OK – 1 posisjon(er) sjekket ...`

Deretter kjører alt automatisk hvert 10. minutt. Første gang Grotanger er
innenfor 800 m av Enkeltstein får du «ankommet»-e-post; når den er mer enn
1200 m unna igjen får du «dratt fra».

---

## Daglig bruk

### Legge til fartøy eller lokaliteter

Rediger `config.yaml` (kan gjøres rett i nettleseren på github.com):

```yaml
fartoy:
  - navn: GROTANGER
    mmsi: 257699000
  - navn: RONJA POLARIS
    mmsi: 257999999      # finn MMSI på vesselfinder.com eller marinetraffic.com

lokaliteter:
  - navn: Enkeltstein
    nr: 11363
    lat: 68.727583
    lon: 16.910167
    radius_m: 800
```

Koordinater til enhver lokalitet finner du åpent hos Fiskeridirektoratet:
`https://api.fiskeridir.no/pub-aqua/api/v1/sites/<lokalitetsnr>`
(feltene `latitude`/`longitude`). Slakterier o.l. legges inn på samme måte
med koordinater og passende radius.

### Slå opp liveposisjon

Lokalt på egen PC (krever Python og en `.env`-fil med BW_CLIENT_ID og
BW_CLIENT_SECRET i samme mappe):

```
pip install -r requirements.txt
python posisjon.py GROTANGER
```

Gir posisjon, fart, kartlenke og avstand til dine lokaliteter.

### Justeringer

- `radius_m`: hvor nær lokaliteten fartøyet må være for «ankomst» (800 m passer
  de fleste; øk hvis fortøyningspunkt/fôrflåte ligger langt fra senterpunktet)
- `stille_varsel_timer`: sett til f.eks. `6` for å bli varslet hvis et fartøy
  slutter å sende AIS (kan indikere at sender er slått av)
- Varslingsfrekvens: cron-linjen i `.github/workflows/monitor.yml`

---

## Begrensninger verdt å vite

- **Åpne AIS-data dekker norsk økonomisk sone** (+ Svalbard/Jan Mayen).
  Fartøy utenfor dette området rapporteres ikke.
- GitHub Actions cron er ikke sekundpresis – kjøringer kan forsinkes 5–15 min
  i travle perioder. For varsling av ankomst/avgang er dette sjelden et problem.
- API-et gir ikke historikk eldre enn 14 dager.

## Videre utbygging (si ifra, så bygger jeg det)

- **Områdekryssing/karantene**: logge når fartøy forlater ett produksjonsområde
  og ankommer et annet, og flagge for kort tid mellom (brakklegging/karantene)
- Flere mottakere, SMS-varsling, daglig oppsummering
- Kart-dashbord med sporene til fartøyene siste 24 t (historic AIS API)
