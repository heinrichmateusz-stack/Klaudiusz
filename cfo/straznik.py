"""Strażnik repozytorium: blokuje commit/push plików, które mogą zawierać dane finansowe.

Uruchamiany:
  - lokalnie przed każdym commitem (hook .githooks/pre-commit, włączany: python -m cfo zabezpiecz),
  - na GitHubie przy każdym pushu i pull requeście (.github/workflows/blokada-danych.yml).
Tylko biblioteka standardowa — działa bez instalowania zależności.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# rozszerzenia typowe dla wyciągów, eksportów, arkuszy i baz
ZABRONIONE_ROZSZERZENIA = {
    ".csv", ".tsv", ".xlsx", ".xlsm", ".xls", ".ods", ".numbers", ".pdf", ".db", ".sqlite", ".sqlite3",
    ".sta", ".mt940", ".940", ".ofx", ".qif", ".xml", ".gsheet", ".zip", ".7z", ".rar",
}
# nazwy plików generowanych przez cfo (mogą zawierać dane)
ZABRONIONE_NAZWY = re.compile(r"(^|/)(dashboard\.json|analiza-\d{4}-\d{2}\.json|konfiguracja\.json|\d{4}-\d{2}-raport-cfo\.md|\.cfo-dane)$")
ZABRONIONE_FOLDERY = re.compile(r"(^|/)(dane|dane-demo|wejscie|wyniki|raporty)/")
# wyjątki: wyłącznie fikcyjne przykłady
DOZWOLONE = re.compile(r"^(przyklady/|cfo/konfiguracja\.przyklad\.json$)")
# polski numer rachunku (IBAN lub 26 cyfr, także w grupach)
RACHUNEK = re.compile(r"\b(?:PL\s?)?\d{2}(?:[ ]?\d{4}){6}\b")
SPRAWDZ_TRESC = {".md", ".txt", ".json", ".html", ".js", ".py", ".yml", ".yaml", ".ini", ".cfg", ".env", ""}


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def _pliki(tryb):
    if tryb == "--staged":
        out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    else:
        out = _git("ls-files", "-z")
    return [p for p in out.split("\0") if p]


def _tresc(path, tryb):
    try:
        if tryb == "--staged":
            return subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8", "ignore")
        return (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


def sprawdz(tryb="--wszystkie"):
    problemy = []
    for p in _pliki(tryb):
        if DOZWOLONE.match(p):
            continue
        ext = Path(p).suffix.lower()
        if ext in ZABRONIONE_ROZSZERZENIA:
            problemy.append(f"{p}: typ pliku {ext} może zawierać dane finansowe")
        elif ZABRONIONE_NAZWY.search(p) or ZABRONIONE_FOLDERY.search(p):
            problemy.append(f"{p}: plik/folder z danymi generowanymi przez cfo")
        elif ext in SPRAWDZ_TRESC:
            for nr, linia in enumerate(_tresc(p, tryb).splitlines(), 1):
                if RACHUNEK.search(linia) and "straznik" not in p:
                    problemy.append(f"{p}:{nr}: wygląda na numer rachunku bankowego")
                    break
    return problemy


def main(argv):
    tryb = argv[0] if argv else "--wszystkie"
    problemy = sprawdz(tryb)
    if problemy:
        print("⛔ BLOKADA: w repozytorium nie mogą znaleźć się dane finansowe.\n")
        print("\n".join("  - " + x for x in problemy))
        print("\nTrzymaj dane w folderze na Google Drive (python -m cfo ustaw-folder ...).")
        print("Jeśli plik jest fikcyjnym przykładem, umieść go w folderze przyklady/.")
        return 1
    print("✅ Brak plików z danymi finansowymi.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
