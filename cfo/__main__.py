"""Użycie:
  python -m cfo init                 # tworzy strukturę folderu danych i konfigurację
  python -m cfo przetworz [RRRR-MM]  # wczytuje nowe pliki, liczy analizę, zapisuje raport i dashboard.json
  python -m cfo demo                 # generuje przykładowe pliki wejściowe (do testów) w folderze danych
Folder danych: zmienna CFO_DANE (domyślnie ./dane)."""
import sys

from . import analiza, baza, raport


def main(argv):
    cmd = argv[0] if argv else "przetworz"
    d = baza.katalog_danych()
    if cmd == "init":
        baza.przygotuj_katalog(d)
        print(f"Gotowe: {d}\nWrzuć pliki do {d}/wejscie/{{bank,czas-pracy,koszty-zespolu}} i uzupełnij {d}/konfiguracja.json")
    elif cmd == "demo":
        from . import demo
        baza.przygotuj_katalog(d)
        demo.generuj(d)
        print(f"Wygenerowano przykładowe dane w {d}")
    elif cmd == "przetworz":
        baza.przygotuj_katalog(d)
        cfg = baza.wczytaj_konfiguracje(d)
        con = baza.polacz(d)
        log = baza.wczytaj_pliki(con, d)
        baza.klasyfikuj(con, cfg)
        w = analiza.analizuj(con, cfg, argv[1] if len(argv) > 1 else None)
        rap = raport.zapisz(d, con, cfg, w, log)
        print("\n".join(log) or "Brak nowych plików.")
        print(f"\nMiesiąc: {w['miesiac']} · raport: {rap}")
        print(f"Rekomendacje: {len(w['rekomendacje'])}")
        for r in w["rekomendacje"]:
            print(f"  P{r['priorytet']} {r['tytul']}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
