"""Parsery plików wejściowych: wyciągi bankowe (CSV/XLSX/PDF), Clockify (CSV/XLSX), koszty zespołu (XLSX/CSV)."""
import re
from pathlib import Path

from .util import (AMOUNT_RE, cell, detect_date_order, find_header, norm, parse_amount, parse_date,
                   parse_hours, parse_month, read_table)


class ParseError(Exception):
    pass


# ---------------------------------------------------------------- Clockify
CLOCKIFY = {
    "date": ["start date", "data rozpoczecia", "data", "date", "dzien", "day"],
    "client": ["client", "klient"],
    "project": ["project", "projekt"],
    "user": ["user", "uzytkownik", "osoba", "member", "pracownik"],
    "hours": ["duration (decimal)", "czas trwania (dziesietnie)", "time (decimal)", "duration (h)", "czas trwania (h)",
              "duration", "czas trwania", "hours", "godziny", "czas"],
    "billable": ["billable", "rozliczalne", "platne", "fakturowane"],
    "desc": ["description", "opis", "task", "zadanie"],
}


def parse_clockify(path: Path):
    rows = read_table(path)
    h, idx = find_header(rows, CLOCKIFY, ["date", "hours", ("client", "project")])
    if h is None:
        raise ParseError("Nie znaleziono kolumn z datą, czasem trwania i klientem/projektem (eksport 'Detailed' z Clockify).")
    body = rows[h + 1:]
    order = detect_date_order([cell(r, idx, "date") for r in body])
    out, bad = [], 0
    for r in body:
        d = parse_date(cell(r, idx, "date"), order)
        hrs = parse_hours(cell(r, idx, "hours"))
        if not d or not hrs or hrs <= 0:
            bad += 1
            continue
        b = norm(cell(r, idx, "billable"))
        out.append({
            "data": d,
            "klient_zrodlo": str(cell(r, idx, "client") or "").strip(),
            "projekt": str(cell(r, idx, "project") or "").strip(),
            "osoba": str(cell(r, idx, "user") or "").strip(),
            "godziny": round(hrs, 4),
            "rozliczalne": 0 if b in ("no", "nie", "false", "0") else 1,
            "opis": str(cell(r, idx, "desc") or "").strip(),
        })
    return out, {"pominiete_wiersze": bad}


# ---------------------------------------------------------------- Bank CSV/XLSX
BANK = {
    "date": ["data operacji", "data transakcji", "data ksiegowania", "data waluty", "data", "date"],
    "amount": ["kwota operacji", "kwota transakcji", "kwota", "amount"],
    "debit": ["obciazenia", "wyplywy", "debet", "debit", "wn"],
    "credit": ["uznania", "wplywy", "kredyt", "credit", "ma"],
    "party": ["nadawca/odbiorca", "nadawca / odbiorca", "dane kontrahenta", "nazwa kontrahenta", "kontrahent",
              "odbiorca/zleceniodawca", "odbiorca / nadawca", "odbiorca", "nadawca", "counterparty"],
    "title": ["tytul operacji", "tytul", "opis operacji", "szczegoly", "opis", "title", "description"],
    "balance": ["saldo po operacji", "saldo po transakcji", "saldo", "balance"],
}


def parse_bank_table(path: Path):
    rows = read_table(path)
    h, idx = find_header(rows, BANK, ["date", ("amount", "debit", "credit")])
    if h is None:
        raise ParseError("Nie znaleziono kolumn z datą i kwotą w wyciągu.")
    body = rows[h + 1:]
    order = detect_date_order([cell(r, idx, "date") for r in body])
    out, bad = [], 0
    for r in body:
        d = parse_date(cell(r, idx, "date"), order)
        if "amount" in idx:
            amt = parse_amount(cell(r, idx, "amount"))
        else:
            de, cr = parse_amount(cell(r, idx, "debit")) or 0, parse_amount(cell(r, idx, "credit")) or 0
            amt = cr - abs(de) if (de or cr) else None
        if not d or amt is None:
            bad += 1
            continue
        out.append({"data": d, "kwota": round(amt, 2), "kontrahent": str(cell(r, idx, "party") or "").strip(),
                    "opis": str(cell(r, idx, "title") or "").strip(), "saldo": parse_amount(cell(r, idx, "balance"))})
    return out, {"pominiete_wiersze": bad, **_reconcile(out)}


# ---------------------------------------------------------------- Bank PDF
DATE_START = re.compile(r"^\s*(\d{2}[.\-/]\d{2}[.\-/]\d{4}|\d{4}-\d{2}-\d{2})")
SKIP = re.compile(r"(strona \d+|page \d+|saldo pocz|saldo kon|suma |razem|data operacji|data ksieg)", re.I)


def parse_bank_pdf(path: Path):
    """Heurystyka: wiersz zaczyna się od daty i zawiera kwotę; kolejne linie bez daty to ciąg opisu.
    Znaki kwot są weryfikowane saldami (jeśli wyciąg je zawiera). Wynik zawsze sprawdzaj: info['uzgodnione']."""
    import pdfplumber
    lines = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            lines += (p.extract_text() or "").splitlines()
    full = norm("\n".join(lines))
    txs, cur, extra = [], None, 0
    for ln in lines:
        m = DATE_START.match(ln)
        bez_dat = re.sub(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b|\b\d{4}-\d{2}(-\d{2})?\b", " ", ln)
        amts = AMOUNT_RE.findall(bez_dat)
        if m and amts and not SKIP.search(norm(ln)):
            if cur:
                txs.append(cur)
            rest = ln[m.end():]
            for a in amts:
                rest = rest.replace(a.strip(), " ")
            cur = {"data": parse_date(m[1]), "kwota": parse_amount(amts[0]),
                   "saldo": parse_amount(amts[-1]) if len(amts) >= 2 else None,
                   "kontrahent": "", "opis": re.sub(r"\s+", " ", rest).strip()}
            extra = 0
        elif cur and ln.strip() and extra < 4 and not SKIP.search(norm(ln)):
            cur["opis"] = (cur["opis"] + " " + ln.strip()).strip()
            extra += 1
    if cur:
        txs.append(cur)
    # znak kwoty z różnicy sald (wyciągi często drukują obciążenia bez minusa)
    for prev, t in zip(txs, txs[1:]):
        if prev["saldo"] is not None and t["saldo"] is not None and t["kwota"] is not None:
            diff = round(t["saldo"] - prev["saldo"], 2)
            if abs(abs(diff) - abs(t["kwota"])) < 0.01:
                t["kwota"] = diff
    info = _reconcile(txs)
    op = re.search(r"saldo pocz\w*[^\d\-]{0,40}(" + AMOUNT_RE.pattern + ")", full)
    cl = re.search(r"saldo ko\w*[^\d\-]{0,40}(" + AMOUNT_RE.pattern + ")", full)
    if op and cl:
        o, c = parse_amount(op[1]), parse_amount(cl[1])
        if txs and txs[0]["saldo"] is not None and txs[0]["kwota"] is not None:
            d0 = round(txs[0]["saldo"] - o, 2)
            if abs(abs(d0) - abs(txs[0]["kwota"])) < 0.01:
                txs[0]["kwota"] = d0
        s = round(sum(t["kwota"] or 0 for t in txs), 2)
        info.update(saldo_poczatkowe=o, saldo_koncowe=c, uzgodnione=abs(o + s - c) < 0.02,
                    roznica=round(o + s - c, 2))
    if not txs:
        raise ParseError("Nie rozpoznano żadnej transakcji w PDF — agent powinien odczytać plik i zapisać CSV obok.")
    return [t for t in txs if t["data"] and t["kwota"] is not None], info


def _reconcile(txs):
    """Sprawdza ciągłość sald: saldo[i-1] + kwota[i] == saldo[i]."""
    pairs = [(a, b) for a, b in zip(txs, txs[1:]) if a.get("saldo") is not None and b.get("saldo") is not None]
    if not pairs:
        return {"uzgodnione": None, "uwaga": "brak sald w pliku — nie można zweryfikować kompletności"}
    bad = sum(1 for a, b in pairs if abs(a["saldo"] + b["kwota"] - b["saldo"]) > 0.02)
    if bad and all(abs(b["saldo"] + a["kwota"] - a["saldo"]) < 0.02 for a, b in pairs):
        return {"uzgodnione": True, "uwaga": "transakcje w kolejności od najnowszej"}
    return {"uzgodnione": bad == 0, "niezgodnosci_sald": bad}


# ---------------------------------------------------------------- Koszty zespołu
PAYROLL = {
    "person": ["pracownik", "osoba", "imie i nazwisko", "nazwisko i imie", "wspolpracownik", "employee", "name"],
    "month": ["miesiac rozliczeniowy", "miesiac", "okres", "month"],
    "cost": ["calkowity koszt pracodawcy", "koszt pracodawcy", "koszt calkowity", "calkowity koszt", "brutto brutto",
             "koszt zespolu", "koszt", "kwota netto faktury", "wynagrodzenie brutto", "kwota", "brutto", "cost"],
    "form": ["forma wspolpracy", "rodzaj umowy", "forma", "umowa"],
    "hours": ["godziny etatu", "wymiar godzin", "godziny"],
}


def parse_payroll(path: Path):
    rows = read_table(path)
    h, idx = find_header(rows, PAYROLL, ["person", "cost"])
    if h is None:
        raise ParseError("Nie znaleziono kolumn 'pracownik/osoba' i 'koszt' w zestawieniu kosztów zespołu.")
    fallback = parse_month(path.stem) or parse_month(path.parent.name)
    out, bad = [], 0
    for r in rows[h + 1:]:
        person = str(cell(r, idx, "person") or "").strip()
        cost = parse_amount(cell(r, idx, "cost"))
        month = parse_month(cell(r, idx, "month"), fallback) if "month" in idx else fallback
        if not person or cost is None or norm(person) in ("razem", "suma", "total") or not month:
            bad += 1
            continue
        out.append({"miesiac": month, "osoba": person, "koszt": round(cost, 2),
                    "forma": str(cell(r, idx, "form") or "").strip(), "godziny_etatu": parse_hours(cell(r, idx, "hours"))})
    if not out and not fallback:
        raise ParseError("Brak kolumny z miesiącem — dodaj ją albo nazwij plik np. koszty-2026-10.xlsx.")
    return out, {"pominiete_wiersze": bad}
