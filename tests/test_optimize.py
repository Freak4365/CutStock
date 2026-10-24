"""Tests für die Optimierungsalgorithmen."""

import pytest

from core.models import Defekt
from core.optimize import (
    OptimierungsErgebnis,
    PlattenVorrat,
    StangenVorrat,
    optimize_1d,
    optimize_1d_ga,
    optimize_2d,
)


# =====================================================================
# 1D – Stangen
# =====================================================================

class TestOptimize1D:

    def test_ein_teil_passt(self):
        """Ein Teil, eine Stange – trivialster Fall."""
        erg = optimize_1d(
            teile=[("Strebe", 500.0, 1)],
            vorrat=[StangenVorrat(1, 2500.0, 1)],
            kerf=3.0,
        )
        assert len(erg.schnittplaene) == 1
        assert len(erg.fehlende_teile) == 0
        plan = erg.schnittplaene[0]
        assert len(plan.platzierungen) == 1
        assert plan.platzierungen[0].laenge == 500.0

    def test_mehrere_teile_eine_stange(self):
        """Mehrere Teile passen auf eine Stange, Kerf wird abgezogen."""
        erg = optimize_1d(
            teile=[("A", 400.0, 2), ("B", 300.0, 1)],
            vorrat=[StangenVorrat(1, 2500.0, 1)],
            kerf=3.0,
        )
        assert len(erg.schnittplaene) == 1
        assert len(erg.fehlende_teile) == 0
        plan = erg.schnittplaene[0]
        assert len(plan.platzierungen) == 3
        # 400 + 3 + 400 + 3 + 300 = 1106 -> Rest = 1394
        verbraucht = 400 + 3 + 400 + 3 + 300
        assert plan.lager_laenge - verbraucht == pytest.approx(1394.0)

    def test_kerf_beruecksichtigt(self):
        """Bei knappen Stangen macht die Kerf den Unterschied."""
        # Stange 1003mm, 2 Teile à 500mm, Kerf 3mm -> 500+3+500 = 1003 ✓
        erg = optimize_1d(
            teile=[("X", 500.0, 2)],
            vorrat=[StangenVorrat(1, 1003.0, 1)],
            kerf=3.0,
        )
        assert len(erg.fehlende_teile) == 0

        # Stange 1002mm -> 500+3+500 = 1003 > 1002 -> nur 1 passt
        erg2 = optimize_1d(
            teile=[("X", 500.0, 2)],
            vorrat=[StangenVorrat(1, 1002.0, 1)],
            kerf=3.0,
        )
        assert len(erg2.fehlende_teile) == 1

    def test_kleine_stangen_zuerst(self):
        """Kleine/Rest-Stangen werden bevorzugt verwendet."""
        erg = optimize_1d(
            teile=[("A", 300.0, 1)],
            vorrat=[
                StangenVorrat(1, 2500.0, 1),
                StangenVorrat(2, 400.0, 1),
            ],
            kerf=3.0,
        )
        assert len(erg.schnittplaene) == 1
        assert erg.schnittplaene[0].lagerstueck_id == 2

    def test_teil_zu_gross(self):
        """Teil passt auf keine Stange -> fehlend."""
        erg = optimize_1d(
            teile=[("Riese", 3000.0, 1)],
            vorrat=[StangenVorrat(1, 2500.0, 5)],
            kerf=3.0,
        )
        assert erg.fehlende_teile == ["Riese"]
        assert len(erg.schnittplaene) == 0

    def test_mehrere_stangen_noetig(self):
        """Teile brauchen mehr als eine Stange."""
        erg = optimize_1d(
            teile=[("A", 2000.0, 3)],
            vorrat=[StangenVorrat(1, 2500.0, 5)],
            kerf=3.0,
        )
        assert len(erg.schnittplaene) == 3
        assert len(erg.fehlende_teile) == 0

    def test_leerer_vorrat(self):
        erg = optimize_1d(
            teile=[("A", 100.0, 1)],
            vorrat=[],
            kerf=3.0,
        )
        assert erg.fehlende_teile == ["A"]

    def test_verschnitt_prozent(self):
        """Verschnitt wird korrekt berechnet."""
        erg = optimize_1d(
            teile=[("A", 1000.0, 1)],
            vorrat=[StangenVorrat(1, 2000.0, 1)],
            kerf=0.0,
        )
        assert erg.gesamt_verschnitt_prozent == pytest.approx(50.0)

    def test_defekt_teilt_stange(self):
        """Ein Defekt in der Mitte teilt die Stange in zwei Segmente."""
        defekte = {1: {1: [Defekt(einzelstueck_id=1,
                                   position=1000, laenge=100)]}}
        erg = optimize_1d(
            teile=[("A", 900.0, 1), ("B", 1300.0, 1)],
            vorrat=[StangenVorrat(1, 2500.0, 1)],
            kerf=3.0,
            defekte=defekte,
        )
        assert len(erg.fehlende_teile) == 0
        assert len(erg.schnittplaene) == 1

    def test_defekt_macht_teil_unmoeglich(self):
        """Defekt macht Stange zu kurz für ein langes Teil."""
        defekte = {1: {1: [Defekt(einzelstueck_id=1,
                                   position=500, laenge=100)]}}
        erg = optimize_1d(
            teile=[("A", 2000.0, 1)],
            vorrat=[StangenVorrat(1, 2500.0, 1)],
            kerf=3.0,
            defekte=defekte,
        )
        assert erg.fehlende_teile == ["A"]


# =====================================================================
# 1D – Genetischer Algorithmus
# =====================================================================

def _plan_signatur(erg: OptimierungsErgebnis):
    """Vergleichbare Darstellung eines Ergebnisses (für Reproduzierbarkeit)."""
    return (
        [(p.lagerstueck_id, p.stueck_nr,
          [(pl.teil_label, pl.laenge, pl.x) for pl in p.platzierungen])
         for p in erg.schnittplaene],
        erg.fehlende_teile,
        erg.gesamt_verschnitt_prozent,
    )


class TestOptimize1DGA:

    def test_weniger_stangen_als_ffd(self):
        """GA findet eine Auslegung mit weniger Stangen als FFD.

        FFD braucht hier 4 Stangen à 1000 mm, optimal sind 3
        (Summe 3110 mm). Mit der alten Fitness (nur platzierte Länge)
        blieb der GA bei der FFD-Lösung hängen.
        """
        laengen = [220.0, 230.0, 250.0, 250.0, 360.0,
                   370.0, 390.0, 400.0, 440.0]
        teile = [(f"T{i}", l, 1) for i, l in enumerate(laengen)]
        vorrat = [StangenVorrat(1, 1000.0, 9)]

        ffd = optimize_1d(teile, vorrat, kerf=0.0)
        ga = optimize_1d_ga(teile, vorrat, kerf=0.0)

        assert len(ffd.schnittplaene) == 4
        assert len(ga.schnittplaene) == 3
        assert ga.fehlende_teile == []
        assert ga.gesamt_verschnitt_prozent < ffd.gesamt_verschnitt_prozent
        # Alle Teile genau einmal verplant
        labels = sorted(pl.teil_label for p in ga.schnittplaene
                        for pl in p.platzierungen)
        assert labels == sorted(t[0] for t in teile)

    @pytest.mark.parametrize("seed", range(5))
    def test_nie_schlechter_als_ffd(self, seed):
        """Auf Zufallsinstanzen ist der GA nie schlechter als FFD."""
        import random
        r = random.Random(seed)
        teile = [(f"T{i}", float(r.randint(10, 90) * 10), r.randint(1, 2))
                 for i in range(6)]
        vorrat = [StangenVorrat(1, 1200.0, 4), StangenVorrat(2, 2500.0, 3)]

        ffd = optimize_1d(teile, vorrat, kerf=3.0)
        ga = optimize_1d_ga(teile, vorrat, kerf=3.0)

        assert len(ga.fehlende_teile) <= len(ffd.fehlende_teile)
        if len(ga.fehlende_teile) == len(ffd.fehlende_teile):
            assert ga.gesamt_verschnitt_prozent <= ffd.gesamt_verschnitt_prozent

    def test_kerf_eingehalten(self):
        """Teile auf einer Stange überlappen nicht und halten den Kerf ein."""
        teile = [("A", 480.0, 3), ("B", 310.0, 4), ("C", 150.0, 3)]
        vorrat = [StangenVorrat(1, 1000.0, 6)]
        kerf = 3.0
        ga = optimize_1d_ga(teile, vorrat, kerf=kerf)
        assert ga.fehlende_teile == []
        for plan in ga.schnittplaene:
            pl = sorted(plan.platzierungen, key=lambda p: p.x)
            for a, b in zip(pl, pl[1:]):
                assert b.x >= a.x + a.laenge + kerf - 1e-9
            assert pl[-1].x + pl[-1].laenge <= 1000.0 + 1e-9

    def test_mit_defekten(self):
        """Mit Defekten: weniger Stangen als FFD, kein Teil im Defekt.

        Stange 1 hat einen Defekt bei 400–450 mm, Stange 2 bei
        600–630 mm. Segmente derselben Stange zählen als eine Stange.
        """
        defekte = {1: {
            1: [Defekt(einzelstueck_id=1, position=400.0, laenge=50.0)],
            2: [Defekt(einzelstueck_id=2, position=600.0, laenge=30.0)],
        }}
        zonen = {1: (400.0, 450.0), 2: (600.0, 630.0)}
        teile = [(f"T{i}", l, 1)
                 for i, l in enumerate([150.0, 450.0, 220.0, 250.0, 470.0])]
        vorrat = [StangenVorrat(1, 1000.0, 5)]

        ffd = optimize_1d(teile, vorrat, kerf=3.0, defekte=defekte)
        ga = optimize_1d_ga(teile, vorrat, kerf=3.0, defekte=defekte)

        assert ga.fehlende_teile == []
        assert len(ffd.schnittplaene) == 3
        assert len(ga.schnittplaene) == 2
        for plan in ga.schnittplaene:
            if plan.stueck_nr in zonen:
                d0, d1 = zonen[plan.stueck_nr]
                for pl in plan.platzierungen:
                    assert pl.x + pl.laenge <= d0 or pl.x >= d1

    def test_reproduzierbar(self):
        """Zwei Läufe mit gleicher Eingabe liefern denselben Plan."""
        teile = [("A", 620.0, 2), ("B", 410.0, 3), ("C", 275.0, 4),
                 ("D", 130.0, 5)]
        vorrat = [StangenVorrat(1, 1500.0, 3), StangenVorrat(2, 3000.0, 3)]
        defekte = {2: {1: [Defekt(einzelstueck_id=1,
                                   position=1200.0, laenge=80.0)]}}
        e1 = optimize_1d_ga(teile, vorrat, kerf=3.0, defekte=defekte)
        e2 = optimize_1d_ga(teile, vorrat, kerf=3.0, defekte=defekte)
        assert _plan_signatur(e1) == _plan_signatur(e2)

    def test_einzelnes_teil(self):
        """Nur ein Teil: kein Absturz (nichts zu permutieren)."""
        ga = optimize_1d_ga([("A", 500.0, 1)], [StangenVorrat(1, 1000.0, 1)])
        assert ga.fehlende_teile == []
        assert len(ga.schnittplaene) == 1


# =====================================================================
# 2D – Platten
# =====================================================================

class TestOptimize2D:

    def test_ein_teil_passt(self):
        """Ein Teil auf eine Platte."""
        erg = optimize_2d(
            teile=[("Boden", 800.0, 300.0, 1)],
            vorrat=[PlattenVorrat(1, 2800.0, 2070.0, 1)],
            kerf=3.0,
        )
        assert len(erg.schnittplaene) == 1
        assert len(erg.fehlende_teile) == 0

    def test_mehrere_teile_eine_platte(self):
        """Mehrere Teile werden auf eine Platte gepackt."""
        erg = optimize_2d(
            teile=[("A", 500.0, 400.0, 3)],
            vorrat=[PlattenVorrat(1, 2000.0, 1000.0, 1)],
            kerf=3.0,
        )
        assert len(erg.fehlende_teile) == 0
        assert len(erg.schnittplaene) == 1

    def test_kerf_bei_platten(self):
        """Kerf wird bei Platzierung berücksichtigt."""
        # Platte 1003 x 500, 2 Teile à 500 x 500, Kerf 3 -> 500+3+500 = 1003 ✓
        erg = optimize_2d(
            teile=[("X", 500.0, 500.0, 2)],
            vorrat=[PlattenVorrat(1, 1003.0, 500.0, 1)],
            kerf=3.0,
            drehung_erlaubt=False,
        )
        assert len(erg.fehlende_teile) == 0

    def test_drehung(self):
        """Teil wird gedreht, wenn es sonst nicht passt."""
        # Platte 1000x400, Teil 300x900 -> passt nicht, gedreht 900x300 -> passt
        erg = optimize_2d(
            teile=[("D", 300.0, 900.0, 1)],
            vorrat=[PlattenVorrat(1, 1000.0, 400.0, 1)],
            kerf=3.0,
            drehung_erlaubt=True,
        )
        assert len(erg.fehlende_teile) == 0
        assert erg.schnittplaene[0].platzierungen[0].gedreht is True

    def test_drehung_verboten(self):
        """Ohne Drehung passt das Teil nicht."""
        erg = optimize_2d(
            teile=[("D", 300.0, 900.0, 1)],
            vorrat=[PlattenVorrat(1, 1000.0, 400.0, 1)],
            kerf=3.0,
            drehung_erlaubt=False,
        )
        assert len(erg.fehlende_teile) == 1

    def test_teil_zu_gross(self):
        erg = optimize_2d(
            teile=[("Riese", 3000.0, 3000.0, 1)],
            vorrat=[PlattenVorrat(1, 2800.0, 2070.0, 2)],
            kerf=3.0,
        )
        assert erg.fehlende_teile == ["Riese"]

    def test_kleine_platten_zuerst(self):
        """Kleine Platten werden bevorzugt (Reste zuerst)."""
        erg = optimize_2d(
            teile=[("A", 200.0, 200.0, 1)],
            vorrat=[
                PlattenVorrat(1, 2800.0, 2070.0, 1),
                PlattenVorrat(2, 300.0, 300.0, 1),
            ],
            kerf=3.0,
        )
        assert erg.schnittplaene[0].lagerstueck_id == 2

    def test_verschnitt_prozent(self):
        erg = optimize_2d(
            teile=[("A", 500.0, 500.0, 1)],
            vorrat=[PlattenVorrat(1, 1000.0, 1000.0, 1)],
            kerf=0.0,
            drehung_erlaubt=False,
        )
        assert erg.gesamt_verschnitt_prozent == pytest.approx(75.0)

    def test_defekt_blockiert_platte(self):
        """Defekt blockiert Fläche — Teil wird daneben platziert."""
        defekte = {1: {1: [Defekt(einzelstueck_id=1,
                                   position=0, position_y=0,
                                   laenge=400, breite=500)]}}
        erg = optimize_2d(
            teile=[("A", 500.0, 400.0, 1)],
            vorrat=[PlattenVorrat(1, 1000.0, 500.0, 1)],
            kerf=3.0,
            drehung_erlaubt=False,
            defekte=defekte,
        )
        assert len(erg.fehlende_teile) == 0
        p = erg.schnittplaene[0].platzierungen[0]
        assert p.x >= 403

    def test_defekt_zu_gross_kein_platz(self):
        """Defekt lässt nicht genug Platz — Teil passt nicht."""
        defekte = {1: {1: [Defekt(einzelstueck_id=1,
                                   position=0, position_y=0,
                                   laenge=600, breite=500)]}}
        erg = optimize_2d(
            teile=[("A", 500.0, 400.0, 1)],
            vorrat=[PlattenVorrat(1, 1000.0, 500.0, 1)],
            kerf=3.0,
            drehung_erlaubt=False,
            defekte=defekte,
        )
        assert len(erg.fehlende_teile) == 1

    def test_guillotine_reste_sind_rechtecke(self):
        """Alle Reste müssen Rechtecke sein (Guillotine-Constraint)."""
        erg = optimize_2d(
            teile=[("A", 600.0, 400.0, 2)],
            vorrat=[PlattenVorrat(1, 2000.0, 1000.0, 1)],
            kerf=3.0,
        )
        for plan in erg.schnittplaene:
            for rest_l, rest_b in plan.reste:
                assert rest_l > 0
                assert rest_b > 0
