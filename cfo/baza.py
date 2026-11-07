"""Folder danych, baza SQLite (lokalna), konfiguracja (klienci.xlsx / konfiguracja.json) i wczytywanie plików."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from . import arkusz, parsers
from .util import norm

ROOT = Path(__file__).resolve().parent.parent
FOLDERY = {"bank": "bank", "czas-pracy": "clockify", "koszty-zespolu": "kadry"}
ROZSZERZENIA = {".csv", ".txt", ".xlsx", ".xlsm", ".pdf"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS pliki (sciezka TEXT PRIMARY KEY, typ TEXT, hash TEXT, wczytano TEXT, wiersze INT, info TEXT);
CREATE TABLE IF NOT EXISTS transakcje (id INTEGER PRIMARY KEY, data TEXT, kwota REAL, kontrahent TEXT, opis TEXT,
  saldo REAL, plik TEXT, kategoria TEXT, klient TEXT, UNIQUE(data, kwota, kontrahent, opis));
CREATE TABLE IF NOT EXISTS godziny (id INTEGER PRIMARY KEY, data TEXT, klient_zrodlo TEXT, projekt TEXT, osoba TEXT,
  godziny REAL, rozliczalne INT, opis TEXT, plik TEXT, klient TEXT);
CREATE TABLE IF NOT EXISTS koszty_zespolu (id INTEGER PRIMARY KEY, miesiac TEXT, osoba TEXT, koszt REAL, forma TEXT,
  godziny_etatu REAL, plik TEXT, UNIQUE(miesiac, osoba));
"""


USTAWIENIE = ROOT / ".cfo-dane"  # lokalny plik (poza gitem) ze ścieżką do folderu danych


def katalog_danych() -> Path:
    """Kolejność: zmienna CFO_DANE, plik .cfo-dane (python -m cfo ustaw-folder), ./dane."""
    if os.environ.get("CFO_DANE"):
        return Path(os.environ["CFO_DANE"]).expanduser().resolve()
    if USTAWIENIE.exists():
        sciezka = USTAWIENIE.read_text(encoding="utf-8").strip()
        if sciezka:
            return Path(sciezka).expanduser().resolve()
    return (ROOT / "dane").resolve()


def czy_w_repozytorium(d: Path) -> bool:
    try:
        d.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def sciezka_bazy(d: Path) -> Path:
    """Baza jest odtwarzalna z plików, więc trzymamy ją lokalnie (nie na Drive) — bez konfliktów synchronizacji."""
    if os.environ.get("CFO_BAZA"):
        return Path(os.environ["CFO_BAZA"])
    klucz = hashlib.sha1(str(d).encode()).hexdigest()[:12]
    p = Path.home() / ".cfo" / klucz
    p.mkdir(parents=True, exist_ok=True)
    return p / "finanse.db"


def przygotuj_katalog(d: Path):
    for f in FOLDERY:
        (d / "wejscie" / f).mkdir(parents=True, exist_ok=True)
    for f in ("wyniki", "raporty"):
        (d / f).mkdir(parents=True, exist_ok=True)
    if not (d / arkusz.PLIK).exists() and not (d / "konfiguracja.json").exists():
        cfg = json.loads((Path(__file__).parent / "konfiguracja.przyklad.json").read_text(encoding="utf-8"))
        arkusz.utworz_szablon(d / arkusz.PLIK, {**cfg, "klienci": [], "zespol": []})


def wczytaj_konfiguracje(d: Path) -> dict:
    """Bazą jest konfiguracja.json (jeśli istnieje) albo wzór; klienci.xlsx nadpisuje sekcje, które zawiera."""
    zrodlo = d / "konfiguracja.json"
    if not zrodlo.exists():
        zrodlo = Path(__file__).parent / "konfiguracja.przyklad.json"
    cfg = json.loads(zrodlo.read_text(encoding="utf-8"))
    if zrodlo.name == "konfiguracja.przyklad.json":
        cfg["klienci"], cfg["zespol"] = [], []
    xlsx = d / arkusz.PLIK
    if xlsx.exists():
        z_arkusza = arkusz.wczytaj(xlsx)
        firma = {**cfg.get("firma", {}), **z_arkusza.pop("firma", {})}
        cfg.update(z_arkusza)
        cfg["firma"] = firma
    cfg.setdefault("firma", {})
    cfg.setdefault("klienci", [])
    cfg.setdefault("zespol", [])
    cfg.setdefault("kategorie", {})
    cfg.setdefault("reguly_kosztow", [])
    return cfg


def polacz(d: Path):
    con = sqlite3.connect(sciezka_bazy(d))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _hash(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wczytaj_pliki(con, d: Path):
    """Wczytuje nowe/zmienione pliki, usuwa dane z plików skasowanych. Zwraca listę komunikatów."""
    log = []
    obecne = set()
    for folder, typ in FOLDERY.items():
        base = d / "wejscie" / folder
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in ROZSZERZENIA or p.name.startswith((".", "~$")):
                continue
            rel = str(p.relative_to(d))
            # PDF z ręcznie/agentowo przygotowanym CSV o tej samej nazwie jest pomijany
            if p.suffix.lower() == ".pdf" and any(p.with_suffix(s).exists() for s in (".csv", ".xlsx")):
                log.append(f"ℹ️ {rel}: pominięty, używam pliku {p.stem}.csv/.xlsx o tej samej nazwie")
                continue
            obecne.add(rel)
            h = _hash(p)
            old = con.execute("SELECT hash FROM pliki WHERE sciezka=?", (rel,)).fetchone()
            if old and old["hash"] == h:
                continue
            _usun_plik(con, rel)
            try:
                if typ == "bank":
                    rows, info = (parsers.parse_bank_pdf if p.suffix.lower() == ".pdf" else parsers.parse_bank_table)(p)
                    n = 0
                    for r in rows:
                        cur = con.execute("INSERT OR IGNORE INTO transakcje(data,kwota,kontrahent,opis,saldo,plik) VALUES(?,?,?,?,?,?)",
                                          (r["data"], r["kwota"], r["kontrahent"], r["opis"], r["saldo"], rel))
                        n += cur.rowcount
                    if n < len(rows):
                        info["duplikaty_pominiete"] = len(rows) - n
                elif typ == "clockify":
                    rows, info = parsers.parse_clockify(p)
                    con.executemany("INSERT INTO godziny(data,klient_zrodlo,projekt,osoba,godziny,rozliczalne,opis,plik) VALUES(?,?,?,?,?,?,?,?)",
                                    [(r["data"], r["klient_zrodlo"], r["projekt"], r["osoba"], r["godziny"], r["rozliczalne"], r["opis"], rel) for r in rows])
                else:
                    rows, info = parsers.parse_payroll(p)
                    con.executemany("INSERT OR REPLACE INTO koszty_zespolu(miesiac,osoba,koszt,forma,godziny_etatu,plik) VALUES(?,?,?,?,?,?)",
                                    [(r["miesiac"], r["osoba"], r["koszt"], r["forma"], r["godziny_etatu"], rel) for r in rows])
                con.execute("INSERT OR REPLACE INTO pliki VALUES(?,?,?,datetime('now'),?,?)",
                            (rel, typ, h, len(rows), json.dumps(info, ensure_ascii=False)))
                ok = info.get("uzgodnione")
                flag = "⚠️" if ok is False else "✅"
                log.append(f"{flag} {rel}: {len(rows)} wierszy {json.dumps(info, ensure_ascii=False)}")
            except Exception as e:  # noqa: BLE001 — chcemy zebrać wszystkie problemy w raporcie
                con.execute("INSERT OR REPLACE INTO pliki VALUES(?,?,?,datetime('now'),0,?)",
                            (rel, typ, h, json.dumps({"blad": str(e)}, ensure_ascii=False)))
                log.append(f"❌ {rel}: {e}")
    for r in con.execute("SELECT sciezka FROM pliki").fetchall():
        if r["sciezka"] not in obecne:
            _usun_plik(con, r["sciezka"])
            con.execute("DELETE FROM pliki WHERE sciezka=?", (r["sciezka"],))
            log.append(f"🗑️ {r['sciezka']}: plik usunięty — usunięto jego dane z bazy")
    con.commit()
    return log


def _usun_plik(con, rel):
    for t in ("transakcje", "godziny", "koszty_zespolu"):
        con.execute(f"DELETE FROM {t} WHERE plik=?", (rel,))


# ---------------------------------------------------------------- dopasowania
def _dopasuj(tekst: str, aliasy) -> bool:
    t = norm(tekst)
    return any(norm(a) and norm(a) in t for a in aliasy)


def klasyfikuj(con, cfg):
    """Przypisuje klientów do godzin i transakcji oraz kategorie kosztów (od nowa przy każdym uruchomieniu)."""
    klienci = cfg["klienci"]
    wlasne = cfg["firma"].get("wlasne_rachunki", [])
    for r in con.execute("SELECT id, klient_zrodlo, projekt FROM godziny").fetchall():
        k = next((c["nazwa"] for c in klienci if _dopasuj(r["klient_zrodlo"], c.get("clockify", []) + [c["nazwa"]])), None)
        if not k:
            k = next((c["nazwa"] for c in klienci if _dopasuj(r["projekt"], c.get("clockify", []))), None)
        con.execute("UPDATE godziny SET klient=? WHERE id=?", (k, r["id"]))
    for r in con.execute("SELECT id, kwota, kontrahent, opis FROM transakcje").fetchall():
        tekst = f"{r['kontrahent']} {r['opis']}"
        kat, kl = None, None
        if _dopasuj(tekst, wlasne):
            kat = "Przelew własny"
        elif r["kwota"] > 0:
            kl = next((c["nazwa"] for c in klienci if _dopasuj(tekst, c.get("bank", []) + [c["nazwa"]])), None)
            kat = "Przychód" if kl else "Wpływ nieprzypisany"
        else:
            kat = next((x["kategoria"] for x in cfg["reguly_kosztow"] if norm(x["zawiera"]) in norm(tekst)), None)
            if not kat:
                osoba = next((z["osoba"] for z in cfg["zespol"] if _dopasuj(tekst, z.get("aliasy", []) + [z["osoba"]])), None)
                kat = "Zespół" if osoba else "Niesklasyfikowane"
        con.execute("UPDATE transakcje SET kategoria=?, klient=? WHERE id=?", (kat, kl, r["id"]))
    con.commit()


def osoba_kanoniczna(cfg, nazwa: str) -> str:
    for z in cfg["zespol"]:
        if norm(nazwa) == norm(z["osoba"]) or any(norm(nazwa) == norm(a) for a in z.get("aliasy", [])):
            return z["osoba"]
    return nazwa
