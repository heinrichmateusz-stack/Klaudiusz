"""Konfiguracja w arkuszu Excel (klienci.xlsx w folderze danych) — łatwa do edycji dla asystentki i księgowej.

Arkusze: Klienci, Zespół, Firma, Reguły kosztów. Wiersze, których nazwa zaczyna się od „PRZYKŁAD”, są pomijane.
"""
from pathlib import Path

from .util import norm, parse_amount, parse_month

PLIK = "klienci.xlsx"

KLIENCI_KOL = ["Nazwa klienta", "Model (godzinowy / ryczałt)", "Stawka netto za godzinę", "Ryczałt netto miesięcznie",
               "Pakiet godzin w ryczałcie", "Ryczałt od (RRRR-MM)", "Ryczałt do (RRRR-MM, puste = bezterminowo)",
               "Termin płatności (dni)", "VAT % (puste = 23)", "Nazwy w banku (po przecinku)", "Nazwy w Clockify (po przecinku)"]
ZESPOL_KOL = ["Osoba (jak w zestawieniu księgowości)", "Inne nazwy: Clockify, e-mail, bank (po przecinku)"]
FIRMA = [  # (etykieta, klucz, wartość domyślna, opis)
    ("Saldo startowe na koncie", "saldo_startowe", 0, "Używane tylko, gdy wyciągi nie zawierają sald"),
    ("VAT od sprzedaży %", "vat_sprzedaz_proc", 23, ""),
    ("VAT od kosztów %", "vat_koszty_proc", 23, "Do przeliczenia kosztów z banku (brutto) na netto"),
    ("Podatek dochodowy %", "podatek_dochodowy_proc", 19, "Do prognozy: płacony w kolejnym miesiącu"),
    ("Docelowa marża %", "docelowa_marza_proc", 30, "Próg dla rekomendacji stawek"),
    ("Godziny etatu miesięcznie", "godziny_etatu_miesiecznie", 160, "Do liczenia obciążenia zespołu"),
    ("Przelewy własne (frazy po przecinku)", "wlasne_rachunki", "przelew własny, przelew wewnętrzny", "Pomijane w cashflow"),
]
REGULY_KOL = ["Fraza w opisie/kontrahencie przelewu", "Kategoria kosztu"]


def _lista(v):
    return [x.strip() for x in str(v or "").replace(";", ",").split(",") if x.strip()]


def utworz_szablon(path: Path, cfg: dict):
    """Tworzy klienci.xlsx: z bieżącej konfiguracji albo z wierszami PRZYKŁAD."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()
    nag = Font(bold=True, color="FFFFFF")
    tlo = PatternFill("solid", fgColor="2F6FED")

    def arkusz(nazwa, kolumny, wiersze, pierwszy=False):
        ws = wb.active if pierwszy else wb.create_sheet()
        ws.title = nazwa
        ws.append(kolumny)
        for c in ws[1]:
            c.font, c.fill = nag, tlo
        for i, k in enumerate(kolumny, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(16, min(42, len(k) + 4))
        for w in wiersze:
            ws.append(w)
        ws.freeze_panes = "A2"
        return ws

    kl = [[c["nazwa"], "ryczałt" if c.get("model") == "ryczalt" else "godzinowy", c.get("stawka"), c.get("ryczalt"),
           c.get("pakiet_godzin"), c.get("od"), c.get("do"), c.get("termin_platnosci_dni", 14), c.get("vat_proc"),
           ", ".join(c.get("bank", [])), ", ".join(c.get("clockify", []))] for c in cfg.get("klienci", [])]
    if not kl:
        kl = [["PRZYKŁAD Alfa Sp. z o.o.", "godzinowy", 180, None, None, None, None, 30, None, "alfa sp, 1234567890", "Alfa"],
              ["PRZYKŁAD Gamma Tech", "ryczałt", None, 12000, 70, "2026-01", None, 14, None, "gamma tech", "Gamma"]]
    ws = arkusz("Klienci", KLIENCI_KOL, kl, pierwszy=True)
    dv = DataValidation(type="list", formula1='"godzinowy,ryczałt"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B2:B500")
    for col in ("F", "G"):
        for r in range(2, 501):
            ws[f"{col}{r}"].number_format = "@"  # miesiące jako tekst RRRR-MM

    ze = [[z["osoba"], ", ".join(z.get("aliasy", []))] for z in cfg.get("zespol", [])] or [["PRZYKŁAD Anna Kowalska", "Anna, anna@firma.pl"]]
    arkusz("Zespół", ZESPOL_KOL, ze)
    f = cfg.get("firma", {})
    fw = []
    for etykieta, klucz, dom, opis in FIRMA:
        v = f.get(klucz, dom)
        fw.append([etykieta, ", ".join(v) if isinstance(v, list) else v, opis])
    arkusz("Firma", ["Parametr", "Wartość", "Opis"], fw)
    re_ = [[r["zawiera"], r["kategoria"]] for r in cfg.get("reguly_kosztow", [])]
    ws = arkusz("Reguły kosztów", REGULY_KOL, re_)
    kat = sorted(cfg.get("kategorie", {}))
    if kat:
        dv = DataValidation(type="list", formula1='"' + ",".join(kat) + '"')
        ws.add_data_validation(dv)
        dv.add("B2:B500")
    wb.save(path)


def wczytaj(path: Path) -> dict:
    """Zwraca fragment konfiguracji (klienci, zespol, firma, reguly_kosztow) z arkusza."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}

    def wiersze(nazwa):
        ws = next((w for w in wb.worksheets if norm(w.title) == norm(nazwa)), None)
        if not ws:
            return None
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        return [r for r in rows if r and r[0] not in (None, "") and not norm(r[0]).startswith("przyklad")]

    def tekst(v):
        return "" if v is None else str(v).strip()

    kl = wiersze("Klienci")
    if kl is not None:
        klienci, bledy = [], []
        for r in kl:
            r = list(r) + [None] * 11
            model = "ryczalt" if norm(r[1]).startswith("rycz") else "godzinowy"
            c = {"nazwa": tekst(r[0]), "model": model, "termin_platnosci_dni": int(parse_amount(r[7]) or 14),
                 "bank": _lista(r[9]), "clockify": _lista(r[10])}
            if model == "ryczalt":
                c.update(ryczalt=parse_amount(r[3]) or 0, pakiet_godzin=parse_amount(r[4]) or 0,
                         od=parse_month(r[5]) or "", do=parse_month(r[6]) or "")
                if not c["ryczalt"]:
                    bledy.append(f"{c['nazwa']}: brak kwoty ryczałtu")
            else:
                c["stawka"] = parse_amount(r[2]) or 0
                if not c["stawka"]:
                    bledy.append(f"{c['nazwa']}: brak stawki godzinowej")
            if r[8] not in (None, ""):
                c["vat_proc"] = parse_amount(r[8])
            klienci.append(c)
        out["klienci"] = klienci
        out["_bledy_arkusza"] = bledy
    ze = wiersze("Zespół")
    if ze is not None:
        out["zespol"] = [{"osoba": tekst(r[0]), "aliasy": _lista(r[1] if len(r) > 1 else "")} for r in ze]
    fi = wiersze("Firma")
    if fi is not None:
        mapa = {norm(e): (k, d) for e, k, d, _ in FIRMA}
        firma = {}
        for r in fi:
            if norm(r[0]) in mapa and len(r) > 1 and r[1] not in (None, ""):
                k, d = mapa[norm(r[0])]
                firma[k] = _lista(r[1]) if isinstance(d, str) else parse_amount(r[1])
        out["firma"] = firma
    rg = wiersze("Reguły kosztów")
    if rg is not None:
        out["reguly_kosztow"] = [{"zawiera": tekst(r[0]), "kategoria": tekst(r[1])} for r in rg if len(r) > 1 and r[1]]
    return out
