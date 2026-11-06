"""Generator przykładowych plików wejściowych (fikcyjne dane) — do testów i prezentacji."""
import csv
import datetime as dt
import json
import random
from pathlib import Path

from .util import month_add, month_range

KLIENCI = [
    {"nazwa": "Alfa Sp. z o.o.", "model": "godzinowy", "stawka": 180, "termin_platnosci_dni": 30, "bank": ["alfa sp"], "clockify": ["Alfa"]},
    {"nazwa": "Beta Studio", "model": "godzinowy", "stawka": 150, "termin_platnosci_dni": 14, "bank": ["beta studio"], "clockify": ["Beta"]},
    {"nazwa": "Epsilon Consulting", "model": "godzinowy", "stawka": 200, "termin_platnosci_dni": 45, "bank": ["epsilon"], "clockify": ["Epsilon"]},
    {"nazwa": "Gamma Tech", "model": "ryczalt", "ryczalt": 12000, "pakiet_godzin": 70, "od": "", "termin_platnosci_dni": 14, "bank": ["gamma tech"], "clockify": ["Gamma"]},
    {"nazwa": "Delta Retail", "model": "ryczalt", "ryczalt": 8000, "pakiet_godzin": 40, "od": "", "termin_platnosci_dni": 30, "bank": ["delta retail"], "clockify": ["Delta"]},
]
ZESPOL = [("Anna Kowalska", "Anna", 11000, "B2B"), ("Piotr Nowak", "Piotr", 9000, "UoP"), ("Kasia Wiśniewska", "Kasia", 7500, "B2B")]
PLAN = {"Alfa": 80, "Beta": 45, "Epsilon": 35, "Gamma": 82, "Delta": 58}


def generuj(d: Path):
    rnd = random.Random(7)
    dzis = dt.date.today()
    koniec = month_add(dzis.strftime("%Y-%m"), -1)
    start = month_add(koniec, -4)
    miesiace = month_range(start, koniec)
    cfg = json.loads((Path(__file__).parent / "konfiguracja.przyklad.json").read_text(encoding="utf-8"))
    cfg["klienci"] = [dict(k, od=start) if k["model"] == "ryczalt" else k for k in KLIENCI]
    cfg["zespol"] = [{"osoba": o, "aliasy": [a]} for o, a, _, _ in ZESPOL]
    cfg["firma"]["saldo_startowe"] = 60000
    (d / "konfiguracja.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Clockify: godziny
    wpisy, przychod = [], {m: {} for m in miesiace}
    for m in miesiace:
        y, mo = map(int, m.split("-"))
        dni = [dt.date(y, mo, x) for x in range(1, 32) if _ok(y, mo, x) and dt.date(y, mo, x).weekday() < 5]
        for proj, cel in PLAN.items():
            if proj == "Epsilon" and m < month_add(start, 2):
                continue
            zostalo, suma = cel * (0.8 + rnd.random() * 0.4), 0
            while zostalo > 0.5:
                g = min(zostalo, round((1 + rnd.random() * 5) * 4) / 4)
                wpisy.append((rnd.choice(dni), proj, rnd.choice(ZESPOL)[1], g, "Yes"))
                zostalo -= g
                suma += g
        for _ in range(6):
            wpisy.append((rnd.choice(dni), "Wewnętrzne", rnd.choice(ZESPOL)[1], 2.0, "No"))
    for data, proj, os, g, b in wpisy:
        k = next((k for k in KLIENCI if proj in k["clockify"]), None)
        if k and k["model"] == "godzinowy" and b == "Yes":
            przychod[data.strftime("%Y-%m")][k["nazwa"]] = przychod[data.strftime("%Y-%m")].get(k["nazwa"], 0) + g * k["stawka"]
    for m in miesiace:
        for k in KLIENCI:
            if k["model"] == "ryczalt":
                przychod[m][k["nazwa"]] = k["ryczalt"]
    wpisy.sort()
    pol = [w for w in wpisy if w[0].strftime("%Y-%m") < miesiace[3]]
    with open(d / "wejscie" / "czas-pracy" / f"clockify-{start}-{miesiace[2]}.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["Project", "Client", "Description", "Task", "User", "Email", "Tags", "Billable", "Start Date", "Start Time",
                     "End Date", "End Time", "Duration (h)", "Duration (decimal)"])
        for data, proj, os, g, b in pol:
            klient = next((k["nazwa"] for k in KLIENCI if proj in k["clockify"]), "")
            hh = f"{int(g):02d}:{int(round(g % 1 * 60)):02d}:00"
            wr.writerow([proj, klient, "Prace projektowe", "", os, "", "", b, data.strftime("%m/%d/%Y"), "09:00:00", data.strftime("%m/%d/%Y"), "", hh, f"{g:.2f}"])
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Projekt", "Klient", "Opis", "Użytkownik", "Rozliczalne", "Data rozpoczęcia", "Czas trwania (h)", "Czas trwania (dziesiętnie)"])
    for data, proj, os, g, b in wpisy:
        if data.strftime("%Y-%m") >= miesiace[3]:
            klient = next((k["nazwa"] for k in KLIENCI if proj in k["clockify"]), "")
            ws.append([proj, klient, "Prace projektowe", os, "Tak" if b == "Yes" else "Nie", data.strftime("%d.%m.%Y"), "", g])
    wb.save(d / "wejscie" / "czas-pracy" / f"clockify-{miesiace[3]}-{koniec}.xlsx")

    # ---- Koszty zespołu z księgowości
    for m in miesiace:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Zestawienie kosztów zespołu", m])
        ws.append([])
        ws.append(["Pracownik", "Forma współpracy", "Całkowity koszt pracodawcy"])
        for o, _, koszt, forma in ZESPOL:
            ws.append([o, forma, koszt])
        ws.append(["Razem", "", sum(z[2] for z in ZESPOL)])
        wb.save(d / "wejscie" / "koszty-zespolu" / f"koszty-zespolu-{m}.xlsx")

    # ---- Bank
    tx = []
    for m in miesiace:
        y, mo = map(int, m.split("-"))
        D = lambda x: dt.date(y, mo, x)  # noqa: E731
        for k in KLIENCI:
            off = -(-k["termin_platnosci_dni"] // 30)
            src = month_add(m, -off)
            if src in przychod and przychod[src].get(k["nazwa"]):
                if k["nazwa"] == "Delta Retail" and m == koniec:
                    continue  # klient spóźnia się z płatnością
                tx.append((D(rnd.randint(8, 20)), round(przychod[src][k["nazwa"]] * 1.23, 2), k["nazwa"].upper(), f"FV/{src}/{k['nazwa'][:4].upper()}"))
        for o, _, koszt, forma in ZESPOL:
            if forma == "B2B":
                tx.append((D(10), -round(koszt * 1.23, 2), o, f"Faktura B2B {o} {month_add(m, -1)}"))
            else:
                tx.append((D(10), -round(koszt * 0.72, 2), o, f"Wynagrodzenie {month_add(m, -1)}"))
        tx.append((D(15), -round(9000 * 0.28 + 1800, 2), "ZAKŁAD UBEZPIECZEŃ SPOŁECZNYCH", "Składki ZUS"))
        tx.append((D(5), -3075.00, "Hub Coworking", "Coworking najem biurka"))
        tx.append((D(3), -round(950 * 1.23 * (1.35 if m == koniec else 1), 2), "Google Ireland / Atlassian", "Google Workspace i Atlassian"))
        tx.append((D(7), -738.00, "Biuro Rachunkowe Bilans", "Biuro rachunkowe usługa"))
        tx.append((D(25), -round(2500 + rnd.random() * 1500, 2), "URZĄD SKARBOWY", "VAT-7 za " + month_add(m, -1)))
        tx.append((D(28), -19.90, "", "Opłata za prowadzenie rachunku"))
        if m == miesiace[2]:
            tx.append((D(12), -1899.00, "Allegro.pl", "Zakup monitor"))
            tx.append((D(14), 450.00, "Jan Kowalski", "Zwrot za bilety"))
    tx.sort()
    saldo, rows = cfg["firma"]["saldo_startowe"], []
    for t in tx:
        saldo = round(saldo + t[1], 2)
        rows.append((*t, saldo))
    csv_rows = [r for r in rows if r[0].strftime("%Y-%m") < koniec]
    with open(d / "wejscie" / "bank" / f"mbank-{start}-{month_add(koniec, -1)}.csv", "w", newline="", encoding="cp1250") as fh:
        fh.write("mBank S.A. Bankowość Detaliczna;\n#Klient;FIRMA DEMO\n#Za okres:;" + start + ";\n\n")
        wr = csv.writer(fh, delimiter=";")
        wr.writerow(["#Data operacji", "#Opis operacji", "#Rachunek", "#Kategoria", "#Kwota", "#Saldo po operacji"])
        for data, kw, kontr, opis, s in csv_rows:
            wr.writerow([data.isoformat(), f"{kontr} {opis}".strip(), "PL00 1140", "", f"{kw:.2f}".replace(".", ",") + " PLN", f"{s:.2f}".replace(".", ",") + " PLN"])
    pdf_rows = [r for r in rows if r[0].strftime("%Y-%m") == koniec]
    otw = csv_rows[-1][4] if csv_rows else cfg["firma"]["saldo_startowe"]
    _pdf(d / "wejscie" / "bank" / f"wyciag-{koniec}.pdf", koniec, otw, pdf_rows)


def _ok(y, mo, x):
    try:
        dt.date(y, mo, x)
        return True
    except ValueError:
        return False


def _fmt(v, znak=True):
    return f"{(v if znak else abs(v)):,.2f}".replace(",", " ").replace(".", ",")


def _pdf(path, m, otw, rows):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    font = "Helvetica"
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if Path(f).exists():
            pdfmetrics.registerFont(TTFont("DejaVu", f))
            font = "DejaVu"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font, 9)
    y = 800
    for line in [f"Wyciąg z rachunku nr 10/{m[:4]}", f"Okres: {m}", f"Saldo początkowe: {_fmt(otw)} PLN", "",
                 "Data operacji   Opis                                               Kwota          Saldo"]:
        c.drawString(40, y, line)
        y -= 14
    for data, kw, kontr, opis, s in rows:
        c.drawString(40, y, data.strftime("%d.%m.%Y"))
        c.drawString(110, y, f"{kontr} {opis}"[:60])
        c.drawRightString(470, y, _fmt(kw, znak=False))  # obciążenia bez minusa — tak drukuje część banków
        c.drawRightString(550, y, _fmt(s))
        y -= 14
        if y < 60:
            c.showPage()
            c.setFont(font, 9)
            y = 800
    c.drawString(40, y - 10, f"Saldo końcowe: {_fmt(rows[-1][4] if rows else otw)} PLN")
    c.save()
