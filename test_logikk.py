"""Enkle tester av geofence-logikken. Kjør: python test_logikk.py"""
from monitor import haversine_m, vurder_overgang

LAT, LON = 68.727583, 16.910167  # Enkeltstein (11363)

def test():
    # Avstandsberegning
    d = haversine_m(LAT, LON, LAT + 1.0, LON)
    assert 110_000 < d < 112_500, d
    d500 = haversine_m(LAT, LON, LAT + 500 / 111_195, LON)
    assert 490 < d500 < 510, d500

    R, H, MF = 800.0, 1.5, 4.0

    # --- Uten fartsgrense (maks_fart_knop = 0): som før ---
    assert vurder_overgang(False, 700, R, H) == (True, "ankomst")
    assert vurder_overgang(False, 900, R, H) == (False, None)
    assert vurder_overgang(True, 1000, R, H) == (True, None)
    assert vurder_overgang(True, 1300, R, H) == (False, "avgang")

    # --- Med fartsgrense 4 knop ---
    # Gjennomfart: innenfor radius i 10 knop -> INGEN ankomst
    assert vurder_overgang(False, 700, R, H, 10.0, MF) == (False, None)
    # Ankomst: innenfor radius i 2 knop
    assert vurder_overgang(False, 700, R, H, 2.0, MF) == (True, "ankomst")
    # Ankomst: innenfor radius, stillestående
    assert vurder_overgang(False, 200, R, H, 0.0, MF) == (True, "ankomst")
    # Manglende fartsdata tolkes som stilleliggende -> ankomst
    assert vurder_overgang(False, 700, R, H, None, MF) == (True, "ankomst")
    # Akkurat på grensen (4.0 knop) teller som ankomst
    assert vurder_overgang(False, 700, R, H, 4.0, MF) == (True, "ankomst")
    # Var på lokaliteten, øker fart innenfor radius -> fortsatt inne, ingen dublett
    assert vurder_overgang(True, 500, R, H, 9.0, MF) == (True, None)
    # Var på lokaliteten, drar i full fart -> AVGANG (fart irrelevant på vei ut)
    assert vurder_overgang(True, 1300, R, H, 11.0, MF) == (False, "avgang")
    # Var på lokaliteten, driver i grensesonen -> fortsatt inne
    assert vurder_overgang(True, 1000, R, H, 1.0, MF) == (True, None)
    # Gjennomfart hele veien: aldri inne, aldri avgang
    inne = False
    for avstand, fart in [(2000, 11), (900, 11), (600, 10), (700, 12), (1500, 11)]:
        inne, h = vurder_overgang(inne, avstand, R, H, fart, MF)
        assert h is None and inne is False, (avstand, fart, inne, h)

    print("Alle tester OK")

if __name__ == "__main__":
    test()
