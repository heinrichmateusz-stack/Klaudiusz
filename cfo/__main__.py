"""Agent CFO — polecenia:
  python -m cfo ustaw-folder ŚCIEŻKA   zapamiętuje folder z danymi (np. folder CFO na Dysku Google)
  python -m cfo init                   tworzy podfoldery i arkusz klienci.xlsx w folderze danych
  python -m cfo przetworz [RRRR-MM]    wczytuje nowe pliki, liczy analizę, zapisuje raport i dashboard.json
  python -m cfo dashboard              otwiera dashboard w przeglądarce z aktualnymi danymi (tylko na tym komputerze)
  python -m cfo szablon                tworzy klienci.xlsx z obecnej konfiguracji (jeśli go nie ma)
  python -m cfo zabezpiecz             włącza blokadę commitowania danych finansowych do gita
  python -m cfo sprawdz                sprawdza, czy w repozytorium nie ma danych finansowych
  python -m cfo demo                   generuje fikcyjne dane testowe w folderze danych
Folder danych: zmienna CFO_DANE, potem ustawienie z 'ustaw-folder', domyślnie ./dane."""
import subprocess
import sys
from pathlib import Path

from . import analiza, arkusz, baza, raport, straznik


def _ostrzez_repo(d: Path):
    if baza.czy_w_repozytorium(d):
        print(f"ℹ️ Folder danych {d} leży w repozytorium (chroni go .gitignore i blokada commitów).\n"
              "   Zalecane: trzymaj dane na Dysku Google — python -m cfo ustaw-folder \"<ścieżka do folderu CFO>\"\n")


def przetworz(d: Path, miesiac=None):
    baza.przygotuj_katalog(d)
    cfg = baza.wczytaj_konfiguracje(d)
    con = baza.polacz(d)
    log = baza.wczytaj_pliki(con, d)
    log += [f"⚠️ klienci.xlsx: {b}" for b in cfg.pop("_bledy_arkusza", [])]
    if not cfg["klienci"]:
        log.append("⚠️ Brak klientów w konfiguracji — uzupełnij arkusz klienci.xlsx")
    baza.klasyfikuj(con, cfg)
    w = analiza.analizuj(con, cfg, miesiac)
    rap = raport.zapisz(d, con, cfg, w, log)
    print("\n".join(log) or "Brak nowych plików.")
    print(f"\nMiesiąc: {w['miesiac']} · raport: {rap}")
    print(f"Rekomendacje: {len(w['rekomendacje'])}")
    for r in w["rekomendacje"]:
        print(f"  P{r['priorytet']} {r['tytul']}")
    return w


def dashboard(d: Path, port=8765):
    """Serwer tylko na 127.0.0.1: udostępnia wyłącznie index.html i dashboard.json — nic więcej z dysku."""
    import http.server
    import webbrowser
    dane = d / "wyniki" / "dashboard.json"
    strona = baza.ROOT / "index.html"

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            sciezka = self.path.split("?")[0]
            plik = {"/": strona, "/index.html": strona, "/dane/wyniki/dashboard.json": dane}.get(sciezka)
            if not plik or not plik.exists():
                self.send_error(404)
                return
            body = plik.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if plik.suffix == ".json" else "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/?baza"
    print(f"Dashboard: {url}  (dostępny tylko na tym komputerze; Ctrl+C kończy)")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv):
    for strumien in (sys.stdout, sys.stderr):  # konsola Windows: bez błędów na emoji/polskich znakach
        try:
            strumien.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    cmd = argv[0] if argv else "przetworz"
    if cmd == "ustaw-folder":
        if len(argv) < 2:
            print("Podaj ścieżkę, np.: python -m cfo ustaw-folder \"G:\\Mój dysk\\CFO\"")
            return 1
        p = Path(argv[1]).expanduser().resolve()
        if not p.exists():
            print(f"Folder {p} nie istnieje — sprawdź, czy Dysk Google jest uruchomiony i ścieżka jest poprawna.")
            return 1
        baza.USTAWIENIE.write_text(str(p), encoding="utf-8")
        print(f"Zapamiętano folder danych: {p}")
        argv, cmd = ["init"], "init"
    if cmd in ("sprawdz", "zabezpiecz"):
        if cmd == "zabezpiecz":
            subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=baza.ROOT, check=True)
            print("Włączono blokadę: każdy commit jest sprawdzany pod kątem danych finansowych.")
        return straznik.main(["--wszystkie"])
    d = baza.katalog_danych()
    if cmd == "init":
        _ostrzez_repo(d)
        baza.przygotuj_katalog(d)
        print(f"Gotowe: {d}\n  • uzupełnij {d / arkusz.PLIK}\n  • wrzucaj pliki do {d / 'wejscie'}/{{bank,czas-pracy,koszty-zespolu}}")
    elif cmd == "szablon":
        cel = d / arkusz.PLIK
        if cel.exists():
            print(f"{cel} już istnieje — nie nadpisuję.")
            return 1
        arkusz.utworz_szablon(cel, baza.wczytaj_konfiguracje(d))
        print(f"Utworzono {cel}")
    elif cmd == "demo":
        from . import demo
        baza.przygotuj_katalog(d)
        demo.generuj(d)
        print(f"Wygenerowano fikcyjne dane w {d}")
    elif cmd == "przetworz":
        _ostrzez_repo(d)
        przetworz(d, argv[1] if len(argv) > 1 else None)
    elif cmd == "dashboard":
        dashboard(d)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
