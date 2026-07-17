"""Enkle tester av geofence-logikken. Kjør: python test_logikk.py"""
from monitor import haversine_m, vurder_overgang

# Enkeltstein (11363)
LAT, LON = 68.727583, 16.910167

def test():
    # Avstandsberegning: ~1 breddegrad = 111,2 km
    d = haversine_m(LAT, LON, LAT + 1.0, LON)
    assert 110_000 < d < 112_500, d

    # Punkt 500 m nord for lokaliteten
    d500 = haversine_m(LAT, LON, LAT + 500 / 111_195, LON)
    assert 490 < d500 < 510, d500

    R, H = 800.0, 1.5

    # Ute -> inne = ankomst
    assert vurder_overgang(False, 700, R, H) == (True, "ankomst")
    # Ute og fortsatt ute = ingenting
    assert vurder_overgang(False, 900, R, H) == (False, None)
    # Inne, driver litt utenfor radius men innenfor hysterese = fortsatt inne
    assert vurder_overgang(True, 1000, R, H) == (True, None)
    # Inne -> godt utenfor = avgang
    assert vurder_overgang(True, 1300, R, H) == (False, "avgang")
    # Inne og fortsatt inne = ingenting
    assert vurder_overgang(True, 200, R, H) == (True, None)
    # Grensetilfeller
    assert vurder_overgang(False, 800, R, H) == (True, "ankomst")
    assert vurder_overgang(True, 1200, R, H) == (True, None)

    print("Alle tester OK")

if __name__ == "__main__":
    test()
