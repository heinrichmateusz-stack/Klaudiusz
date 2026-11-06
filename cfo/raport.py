"""Raport miesięczny (Markdown), plik analizy (JSON) i eksport danych do dashboardu (index.html)."""
import json
import re

from .analiza import WEWN
from .util import norm


def zl(v):
    return "—" if v is None else f"{v:,.0f} zł".replace(",", " ")


def pr(v):
    return "—" if v is None else f"{v * 100:.0f}%"


def h(v):
    return "—" if v is None else f"{v:,.1f} h".replace(",", " ").replace(".", ",")


def _tab(naglowki, wiersze):
    out = ["| " + " | ".join(naglowki) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(naglowki))) + "|"]
    out += ["| " + " | ".join(str(c) for c in w) + " |" for w in wiersze]
    return "\n".join(out)


def raport_md(w, log):
    M, m, okno = w["dane_miesieczne"], w["miesiac"], w["okno_3m"]
    d = M[m]
    p = M.get(w["miesiace"][-2]) if len(w["miesiace"]) > 1 else None
    L = [f"# Raport CFO — {m}", "",
         "> Sekcje liczbowe generuje `python -m cfo przetworz`. Sekcję **Komentarz CFO** uzupełnia agent.", "",
         "## 1. Wynik miesiąca", "",
         _tab(["Pozycja", m, "poprzedni mies.", "średnia 3 mies."], [
             ["Przychód netto", zl(d["przychod"]), zl(p and p["przychod"]), zl(sum(M[x]["przychod"] for x in okno) / len(okno))],
             ["Koszty netto", zl(d["koszty"]), zl(p and p["koszty"]), zl(sum(M[x]["koszty"] for x in okno) / len(okno))],
             ["  w tym zespół (" + d["koszty_zespolu_zrodlo"] + ")", zl(d["koszty_zespolu"]), zl(p and p["koszty_zespolu"]), ""],
             ["Zysk operacyjny", zl(d["zysk"]), zl(p and p["zysk"]), zl(sum(M[x]["zysk"] for x in okno) / len(okno))],
             ["Marża", pr(d["marza"]), pr(p and p["marza"]), ""],
             ["Godziny (rozliczalne)", f"{h(d['godziny'])} ({h(d['godziny_rozliczalne'])})", h(p and p["godziny"]), ""],
             ["Koszt godziny pracy", zl(d["koszt_godziny"]), zl(p and p["koszt_godziny"]), ""],
             ["Wpływy (bank)", zl(d["wplywy"]), zl(p and p["wplywy"]), ""],
             ["Wydatki (bank)", zl(d["wydatki"]), zl(p and p["wydatki"]), ""],
             ["Saldo na koniec" + (" (szacowane)" if d["saldo_szacowane"] else ""), zl(d["saldo"]), zl(p and p["saldo"]), ""],
         ]), "",
         "## 2. Rentowność klientów (ostatnie 3 miesiące)", "",
         _tab(["Klient", "Model", "Godziny", "Przychód", "Koszt", "Marża", "Marża %", "Efekt. stawka", "Koszt h", "Pakiet"],
              [[k["klient"], k["model"], h(k["godziny_3m"]), zl(k["przychod_3m"]), zl(k["koszt_3m"]), zl(k["marza_3m"]),
                pr(k["marza_proc"]), zl(k["efektywna_stawka"]), zl(k["koszt_godziny"]), pr(k["wykorzystanie_pakietu"])] for k in w["klienci"]]),
         "", "## 3. Zespół (ostatnie 3 miesiące)", "",
         _tab(["Osoba", "Godziny", "Rozliczalne", "Obciążenie", "Koszt", "Koszt h"],
              [[z["osoba"], h(z["godziny_3m"]), pr(z["udzial_rozliczalnych"]), pr(z["obciazenie"]), zl(z["koszt_3m"]), zl(z["koszt_godziny"])] for z in w["zespol"]]),
         "", "## 4. Koszty wg kategorii (netto, " + m + ")", "",
         _tab(["Kategoria", "Kwota"], [["Zespół", zl(d["koszty_zespolu"])]] + [[k, zl(v)] for k, v in sorted(d["koszty_inne"].items(), key=lambda x: -x[1])]),
         "", "## 5. Należności", ""]
    n = w["naleznosci"]
    if n["dostepne"]:
        L += [f"Porównanie od {n['od']}: przychód brutto po terminie płatności vs wpływy na konto.", "",
              _tab(["Klient", "Powinno wpłynąć", "Wpłynęło", "Zaległe", "Przed terminem"],
                   [[x["klient"], zl(x["oczekiwane"]), zl(x["wplynelo"]), zl(x["zalegle"]), zl(x["w_drodze"])] for x in n["klienci"]]),
              "", f"**Razem zaległe: {zl(n['zalegle'])} · przed terminem: {zl(n['w_drodze'])}**"]
    else:
        L.append("Brak danych bankowych — nie można uzgodnić należności.")
    L += ["", "## 6. Prognoza 6 miesięcy", "",
          "Bazowa: godziny jak średnia 3 mies., terminowe płatności, zaległości wpływają w 1. miesiącu. "
          "Ostrożna (test warunków skrajnych): −25% godzin u klientów godzinowych, wszystkie płatności przesunięte o miesiąc "
          "(stąd luka we wpływach w 1. miesiącu), zaległości nie wpływają.", ""]
    b, o = w["prognoza"]["bazowa"], w["prognoza"]["ostrozna"]
    L.append(_tab(["Miesiąc", "Przychód", "Koszty", "Zysk", "Wpływy", "Wydatki", "Saldo (bazowa)", "Saldo (ostrożna)"],
                  [[x["miesiac"], zl(x["przychod"]), zl(x["koszty"]), zl(x["zysk"]), zl(x["wplywy"]), zl(x["wydatki"]), zl(x["saldo"]), zl(y["saldo"])]
                   for x, y in zip(b, o)]))
    L += ["", "## 7. Rekomendacje automatyczne", ""]
    for r in w["rekomendacje"]:
        wp = f" _(wpływ ≈ {zl(r['wplyw_mies_pln'])}/mies.)_" if r["wplyw_mies_pln"] else ""
        L.append(f"- **P{r['priorytet']} · {r['tytul']}** — {r['opis']}{wp}")
    if not w["rekomendacje"]:
        L.append("- Brak alertów.")
    L += ["", "## 8. Jakość danych", ""]
    L += [f"- {x}" for x in log] or ["- Brak nowych plików w tym przebiegu."]
    nk = d["nieprzypisane_transakcje"]
    if nk:
        L += ["", "Transakcje bez kategorii / klienta:", "",
              _tab(["Data", "Kwota", "Kontrahent", "Opis"], [[t["data"], zl(t["kwota"]), t["kontrahent"], t["opis"]] for t in nk[:40]])]
    bez = [k["klient"] for k in w["klienci"] if k["model"] == "brak w konfiguracji" and k["klient"] != WEWN]
    if bez:
        L.append(f"\nKlienci z Clockify bez konfiguracji: {', '.join(bez)} — dodaj ich do konfiguracja.json.")
    L += ["", "## 9. Komentarz CFO", "", "_(do uzupełnienia przez agenta — patrz CLAUDE.md)_", ""]
    return "\n".join(L)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-") or "x"


def eksport_dashboard(con, cfg, w):
    """Stan w formacie index.html: klienci, godziny, koszty (faktyczne netto) i cashflow z banku (actuals)."""
    M = w["dane_miesieczne"]
    klienci = []
    for c in cfg["klienci"]:
        r = c.get("model") == "ryczalt"
        klienci.append({"id": _slug(c["nazwa"]), "name": c["nazwa"], "type": "retainer" if r else "hourly",
                        "rate": c.get("stawka", 0), "fee": c.get("ryczalt", 0), "includedHours": c.get("pakiet_godzin", 0),
                        "paymentDays": c.get("termin_platnosci_dni", 14), "startMonth": c.get("od", "") if r else "", "endMonth": c.get("do", "") if r else ""})
    typ = {c["nazwa"]: c.get("model") for c in cfg["klienci"]}
    entries = []
    q = "SELECT data, klient, osoba, SUM(godziny) g FROM godziny WHERE klient IS NOT NULL AND data <= ? AND (rozliczalne=1 OR klient IN (%s)) GROUP BY data, klient, osoba"
    ryczalty = [n for n, t in typ.items() if t == "ryczalt"]
    for i, r in enumerate(con.execute(q % ",".join("?" * len(ryczalty)), [w["miesiac"] + "-31", *ryczalty])):
        entries.append({"id": f"e{i}", "date": r["data"], "clientId": _slug(r["klient"]), "person": r["osoba"], "hours": round(r["g"], 2), "desc": ""})
    costs = []
    for m in w["miesiace"]:
        d = M[m]
        if d["koszty_zespolu"]:
            costs.append({"id": f"k{m}z", "name": "Zespół", "category": "Wynagrodzenia", "type": "once", "amount": round(d["koszty_zespolu"], 2), "month": m})
        for k, v in d["koszty_inne"].items():
            costs.append({"id": f"k{m}{_slug(k)}", "name": k, "category": k, "type": "once", "amount": round(v, 2), "month": m})
    prog = w["prognoza"]["bazowa"]
    if prog:
        costs.append({"id": "prognoza", "name": "Koszty — prognoza (śr. 3 mies.)", "category": "Prognoza", "type": "recurring",
                      "amount": round(prog[0]["koszty"], 2), "startMonth": prog[0]["miesiac"], "endMonth": ""})
    actuals = {m: {"inflow": round(M[m]["wplywy"], 2), "outflow": round(M[m]["wydatki"], 2), "balance": M[m]["saldo"]} for m in w["miesiace"] if M[m]["bank"]}
    first = w["miesiace"][0]
    opening = M[first]["saldo"] - M[first]["wplywy"] + M[first]["wydatki"] if M[first]["bank"] else cfg["firma"].get("saldo_startowe", 0)
    return {"clients": klienci, "entries": entries, "costs": costs, "imports": [], "actuals": actuals,
            "settings": {"openingBalance": round(opening, 2), "openingMonth": first, "costMode": "auto", "manualCostRate": 0,
                         "taxRate": cfg["firma"].get("podatek_dochodowy_proc", 0)},
            "source": "agent", "generatedFor": w["miesiac"]}


def zapisz(d, con, cfg, w, log):
    m = w["miesiac"]
    (d / "wyniki" / f"analiza-{m}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (d / "wyniki" / "dashboard.json").write_text(json.dumps(eksport_dashboard(con, cfg, w), ensure_ascii=False), encoding="utf-8")
    rap = d / "raporty" / f"{m}-raport-cfo.md"
    tresc = raport_md(w, log)
    if rap.exists():  # zachowaj komentarz CFO napisany wcześniej przez agenta
        stary = rap.read_text(encoding="utf-8")
        if "## 9. Komentarz CFO" in stary and "_(do uzupełnienia" not in stary.split("## 9. Komentarz CFO")[1]:
            tresc = tresc.split("## 9. Komentarz CFO")[0] + "## 9. Komentarz CFO" + stary.split("## 9. Komentarz CFO")[1]
    rap.write_text(tresc, encoding="utf-8")
    return rap
