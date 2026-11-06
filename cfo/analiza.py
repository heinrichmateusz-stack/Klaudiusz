"""Model finansowy: wynik memoriałowy (godziny/ryczałty vs koszty), cashflow z banku, należności, prognoza i rekomendacje."""
import datetime as dt
from collections import defaultdict

from .baza import osoba_kanoniczna
from .util import month_add, month_range

WEWN = "(wewnętrzne / nieprzypisane)"


def dd():
    return defaultdict(float)


def _kat(cfg, nazwa):
    k = cfg["kategorie"].get(nazwa)
    if k:
        return k
    if nazwa in ("Przychód", "Wpływ nieprzypisany"):
        return {"rachunek_wynikow": False, "vat": False}
    return {"rachunek_wynikow": True, "vat": True}  # Niesklasyfikowane / nieznane


def _aktywny(c, m):
    return c.get("model") == "ryczalt" and (not c.get("od") or c["od"] <= m) and (not c.get("do") or m <= c["do"])


def _offset(c):
    d = int(c.get("termin_platnosci_dni", 14) or 0)
    return 0 if d <= 0 else -(-d // 30)


def analizuj(con, cfg, miesiac=None):
    f = cfg["firma"]
    vat_k = f.get("vat_koszty_proc", 23) / 100
    klienci = {c["nazwa"]: c for c in cfg["klienci"]}
    vat_c = {n: c.get("vat_proc", f.get("vat_sprzedaz_proc", 23)) / 100 for n, c in klienci.items()}
    godz = con.execute("SELECT * FROM godziny").fetchall()
    tx = con.execute("SELECT * FROM transakcje ORDER BY data, id").fetchall()
    kadry = con.execute("SELECT * FROM koszty_zespolu").fetchall()

    wszystkie = [g["data"][:7] for g in godz] + [t["data"][:7] for t in tx] + [k["miesiac"] for k in kadry]
    if not wszystkie:
        raise SystemExit("Brak danych — wrzuć pliki do dane/wejscie/{bank,czas-pracy,koszty-zespolu}/")
    biezacy = dt.date.today().strftime("%Y-%m")
    if not miesiac:
        ost = max([g["data"][:7] for g in godz] + [t["data"][:7] for t in tx] or wszystkie)
        miesiac = month_add(biezacy, -1) if ost >= biezacy else ost
    start = min(wszystkie)
    miesiace = month_range(start, miesiac)

    # ---------------- godziny
    H = {m: {"klient": dd(), "klient_rozl": dd(), "osoba": dd(), "osoba_rozl": dd(), "kp": dd()} for m in miesiace}
    for g in godz:
        m = g["data"][:7]
        if m not in H:
            continue
        c, p, h = g["klient"] or WEWN, osoba_kanoniczna(cfg, g["osoba"] or "?"), g["godziny"]
        H[m]["klient"][c] += h
        H[m]["osoba"][p] += h
        H[m]["kp"][(c, p)] += h
        if g["rozliczalne"] and g["klient"]:
            H[m]["klient_rozl"][c] += h
            H[m]["osoba_rozl"][p] += h

    # ---------------- kadry
    K = defaultdict(dict)
    etaty = {}
    for k in kadry:
        K[k["miesiac"]][osoba_kanoniczna(cfg, k["osoba"])] = k["koszt"]
        if k["godziny_etatu"]:
            etaty[osoba_kanoniczna(cfg, k["osoba"])] = k["godziny_etatu"]

    # ---------------- bank
    B = {m: {"wplywy": 0.0, "wydatki": 0.0, "saldo": None, "wplywy_klient": dd(), "kat_brutto": dd(), "kat_netto": dd(),
             "jest": False, "nieprzypisane": []} for m in miesiace}
    for t in tx:
        m = t["data"][:7]
        if m not in B:
            continue
        b = B[m]
        b["jest"] = True
        kat = _kat(cfg, t["kategoria"])
        if t["saldo"] is not None:
            b["saldo"] = t["saldo"]
        if kat.get("pomin_w_cashflow"):
            continue
        if t["kwota"] > 0:
            b["wplywy"] += t["kwota"]
            if t["klient"]:
                b["wplywy_klient"][t["klient"]] += t["kwota"]
        else:
            b["wydatki"] += -t["kwota"]
            b["kat_brutto"][t["kategoria"]] += -t["kwota"]
            if kat.get("rachunek_wynikow"):
                b["kat_netto"][t["kategoria"]] += -t["kwota"] / (1 + vat_k) if kat.get("vat") else -t["kwota"]
        if t["kategoria"] in ("Wpływ nieprzypisany", "Niesklasyfikowane"):
            b["nieprzypisane"].append({"data": t["data"], "kwota": t["kwota"], "kontrahent": t["kontrahent"], "opis": t["opis"][:120]})
    saldo = f.get("saldo_startowe", 0) or 0
    for m in miesiace:
        b = B[m]
        if b["saldo"] is None:
            saldo += b["wplywy"] - b["wydatki"]
            b["saldo"] = saldo
            b["saldo_szacowane"] = True
        else:
            saldo = b["saldo"]

    # ---------------- miesiące: wynik memoriałowy i rentowność
    M = {}
    for m in miesiace:
        h, b = H[m], B[m]
        przych = {}
        for n, c in klienci.items():
            if c.get("model") == "ryczalt":
                przych[n] = float(c.get("ryczalt", 0)) if _aktywny(c, m) else 0.0
            else:
                przych[n] = h["klient_rozl"].get(n, 0) * float(c.get("stawka", 0))
        zespol_kadry = sum(K[m].values()) if K.get(m) else None
        zespol_bank = sum(v for k, v in b["kat_netto"].items() if _kat(cfg, k).get("zespol"))
        zespol = zespol_kadry if zespol_kadry is not None else zespol_bank
        inne = {k: v for k, v in b["kat_netto"].items() if not _kat(cfg, k).get("zespol")}
        koszty = zespol + sum(inne.values())
        godz_suma = sum(h["klient"].values())
        stawka_osoby = {p: K[m][p] / h["osoba"][p] for p in K.get(m, {}) if h["osoba"].get(p)}
        koszt_kl = dd()
        for c in h["klient"]:
            if godz_suma == 0:
                break
            narzut = sum(inne.values()) * h["klient"][c] / godz_suma
            if stawka_osoby:
                koszt_kl[c] = sum(v * stawka_osoby.get(p, 0) for (cc, p), v in h["kp"].items() if cc == c) + narzut
            else:
                koszt_kl[c] = koszty * h["klient"][c] / godz_suma
        przychod = sum(przych.values())
        zysk = przychod - koszty
        M[m] = {
            "miesiac": m, "przychod": przychod, "przychod_klient": przych, "koszty": koszty, "koszty_zespolu": zespol,
            "koszty_zespolu_zrodlo": "kadry" if zespol_kadry is not None else "bank", "koszty_inne": inne,
            "zysk": zysk, "marza": zysk / przychod if przychod else None, "godziny": godz_suma,
            "godziny_rozliczalne": sum(h["klient_rozl"].values()), "godziny_klient": dict(h["klient"]),
            "godziny_osoba": dict(h["osoba"]), "godziny_osoba_rozl": dict(h["osoba_rozl"]),
            "koszt_godziny": koszty / godz_suma if godz_suma else None, "koszt_osoby": dict(K.get(m, {})),
            "stawka_osoby": stawka_osoby, "koszt_klienta": dict(koszt_kl), "nieprzypisane_koszty": koszty - sum(koszt_kl.values()),
            "bank": b["jest"], "wplywy": b["wplywy"], "wydatki": b["wydatki"], "saldo": b["saldo"],
            "saldo_szacowane": b.get("saldo_szacowane", False), "wplywy_klient": dict(b["wplywy_klient"]),
            "wydatki_kategorie": dict(b["kat_brutto"]), "nieprzypisane_transakcje": b["nieprzypisane"],
            "vat_szac": sum(przych[n] * vat_c[n] for n in przych) - sum(v * vat_k for k, v in inne.items() if _kat(cfg, k).get("vat")),
            "podatek_szac": max(0.0, zysk) * f.get("podatek_dochodowy_proc", 0) / 100,
        }

    okno = [m for m in miesiace if m >= month_add(miesiac, -2)]
    wynik = {
        "miesiac": miesiac, "miesiace": miesiace, "okno_3m": okno, "dane_miesieczne": M,
        "klienci": _klienci(cfg, M, okno, miesiac),
        "zespol": _zespol(cfg, M, okno, etaty),
        "naleznosci": _naleznosci(cfg, M, miesiace, miesiac, vat_c),
    }
    wynik["prognoza"] = {
        "bazowa": _prognoza(cfg, M, miesiac, wynik["naleznosci"], vat_c, 1.0, 0, True),
        "ostrozna": _prognoza(cfg, M, miesiac, wynik["naleznosci"], vat_c, 0.75, 1, False),
    }
    wynik["rekomendacje"] = _rekomendacje(cfg, wynik)
    return wynik


def _zl(v):
    return f"{v:,.0f} zł".replace(",", " ")


def _sr(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _klienci(cfg, M, okno, miesiac):
    out = []
    nazwy = {c["nazwa"] for c in cfg["klienci"]} | {k for m in okno for k in M[m]["godziny_klient"]}
    cfgk = {c["nazwa"]: c for c in cfg["klienci"]}
    for n in sorted(nazwy):
        c = cfgk.get(n, {})
        g = sum(M[m]["godziny_klient"].get(n, 0) for m in okno)
        p = sum(M[m]["przychod_klient"].get(n, 0) for m in okno)
        k = sum(M[m]["koszt_klienta"].get(n, 0) for m in okno)
        if not g and not p:
            continue
        aktywne = sum(1 for m in okno if _aktywny(c, m)) if c.get("model") == "ryczalt" else None
        pakiet = (c.get("pakiet_godzin") or 0) * (aktywne or 0)
        out.append({
            "klient": n, "model": "wewnętrzne" if n == WEWN else c.get("model", "brak w konfiguracji"), "godziny_3m": g, "przychod_3m": p, "koszt_3m": k,
            "marza_3m": p - k, "marza_proc": (p - k) / p if p else None, "efektywna_stawka": p / g if g else None,
            "koszt_godziny": k / g if g else None, "stawka": c.get("stawka"), "ryczalt": c.get("ryczalt"),
            "pakiet_3m": pakiet or None, "wykorzystanie_pakietu": g / pakiet if pakiet else None,
            "godziny_mies": M[miesiac]["godziny_klient"].get(n, 0), "przychod_mies": M[miesiac]["przychod_klient"].get(n, 0),
        })
    return sorted(out, key=lambda x: -x["marza_3m"])


def _zespol(cfg, M, okno, etaty):
    osoby = sorted({p for m in okno for p in list(M[m]["godziny_osoba"]) + list(M[m]["koszt_osoby"])})
    norma = cfg["firma"].get("godziny_etatu_miesiecznie", 160)
    out = []
    for p in osoby:
        g = sum(M[m]["godziny_osoba"].get(p, 0) for m in okno)
        gr = sum(M[m]["godziny_osoba_rozl"].get(p, 0) for m in okno)
        k = sum(M[m]["koszt_osoby"].get(p, 0) for m in okno)
        mies = len(okno)
        out.append({"osoba": p, "godziny_3m": g, "godziny_rozliczalne_3m": gr, "koszt_3m": k,
                    "koszt_godziny": k / g if g and k else None, "udzial_rozliczalnych": gr / g if g else None,
                    "obciazenie": g / ((etaty.get(p) or norma) * mies) if mies else None})
    return out


def _naleznosci(cfg, M, miesiace, miesiac, vat_c):
    """Porównanie: ile powinno wpłynąć (przychód brutto po terminie płatności) vs ile wpłynęło od klienta."""
    if not any(M[m]["bank"] for m in miesiace):
        return {"dostepne": False, "klienci": [], "zalegle": 0.0, "w_drodze": 0.0}
    start = next(m for m in miesiace if M[m]["bank"])
    out = []
    for c in cfg["klienci"]:
        n, off = c["nazwa"], _offset(c)
        oczek = sum(M[m]["przychod_klient"].get(n, 0) * (1 + vat_c[n]) for m in miesiace
                    if month_add(m, off) <= miesiac and month_add(m, off) >= start)
        wplyw = sum(M[m]["wplywy_klient"].get(n, 0) for m in miesiace if m >= start)
        w_drodze = sum(M[m]["przychod_klient"].get(n, 0) * (1 + vat_c[n]) for m in miesiace if month_add(m, off) > miesiac)
        if oczek or wplyw or w_drodze:
            out.append({"klient": n, "oczekiwane": oczek, "wplynelo": wplyw, "zalegle": max(0.0, oczek - wplyw),
                        "nadplata_lub_wczesniejsze": max(0.0, wplyw - oczek), "w_drodze": w_drodze})
    return {"dostepne": True, "od": start, "klienci": out, "zalegle": sum(x["zalegle"] for x in out),
            "w_drodze": sum(x["w_drodze"] for x in out)}


def _prognoza(cfg, M, miesiac, nal, vat_c, wsp_godzin, opoznienie, zaleglosci, n=6):
    f = cfg["firma"]
    okno = [month_add(miesiac, -i) for i in range(3) if month_add(miesiac, -i) in M]
    zespol = next((sum(M[m]["koszt_osoby"].values()) for m in okno if M[m]["koszt_osoby"]), None)
    if zespol is None:
        zespol = _sr([M[m]["koszty_zespolu"] for m in okno])
    inne_netto = _sr([sum(M[m]["koszty_inne"].values()) for m in okno])
    kat_pomin = {k for k, v in cfg["kategorie"].items() if v.get("zespol") or not v.get("rachunek_wynikow")}
    inne_brutto = _sr([sum(v for k, v in M[m]["wydatki_kategorie"].items() if k not in kat_pomin) for m in okno if M[m]["bank"]]) or inne_netto * 1.23
    przych = {}  # miesiąc -> klient -> netto
    for m in M:
        przych[m] = dict(M[m]["przychod_klient"])
    rows = []
    saldo = M[miesiac]["saldo"]
    poprz_vat, poprz_podatek = M[miesiac]["vat_szac"], M[miesiac]["podatek_szac"]
    for i in range(1, n + 1):
        m = month_add(miesiac, i)
        przych[m] = {}
        for c in cfg["klienci"]:
            nm = c["nazwa"]
            if c.get("model") == "ryczalt":
                przych[m][nm] = float(c.get("ryczalt", 0)) if _aktywny(c, m) else 0.0
            else:
                h = _sr([M[x]["godziny_klient"].get(nm, 0) for x in okno]) if any(M[x]["godziny_klient"].get(nm) for x in okno) else 0
                rozl = sum(M[x]["godziny_rozliczalne"] for x in okno) / max(1e-9, sum(M[x]["godziny"] for x in okno)) if okno else 1
                przych[m][nm] = h * rozl * wsp_godzin * float(c.get("stawka", 0))
        wplywy = 0.0
        for c in cfg["klienci"]:
            zrodlo = month_add(m, -(_offset(c) + opoznienie))
            # przyszły przychód albo faktura z przeszłości, której termin płatności jeszcze nie minął
            if zrodlo > miesiac or month_add(zrodlo, _offset(c)) > miesiac:
                wplywy += przych.get(zrodlo, {}).get(c["nazwa"], 0) * (1 + vat_c[c["nazwa"]])
        if i == 1 and zaleglosci:
            wplywy += nal.get("zalegle", 0)
        przychod = sum(przych[m].values())
        koszty = zespol + inne_netto
        wydatki = zespol + inne_brutto + max(0.0, poprz_vat) + poprz_podatek
        saldo = (saldo or 0) + wplywy - wydatki
        zysk = przychod - koszty
        rows.append({"miesiac": m, "przychod": przychod, "koszty": koszty, "zysk": zysk, "wplywy": wplywy, "wydatki": wydatki, "saldo": saldo})
        poprz_vat = sum(przych[m][k] * vat_c[k] for k in przych[m]) - inne_netto * f.get("vat_koszty_proc", 23) / 100
        poprz_podatek = max(0.0, zysk) * f.get("podatek_dochodowy_proc", 0) / 100
    return rows


def _rekomendacje(cfg, w):
    f = cfg["firma"]
    R = []
    M, okno, m = w["dane_miesieczne"], w["okno_3m"], w["miesiac"]
    cel = f.get("docelowa_marza_proc", 30) / 100
    mies = len(okno)
    koszt_h = _sr([M[x]["koszt_godziny"] for x in okno])
    stawki = [c["stawka"] for c in cfg["klienci"] if c.get("model") != "ryczalt" and c.get("stawka")]
    stawka_ref = _sr(stawki)

    def add(prio, tytul, opis, wplyw=None):
        R.append({"priorytet": prio, "tytul": tytul, "opis": opis, "wplyw_mies_pln": round(wplyw) if wplyw else None})

    for k in w["klienci"]:
        if k["klient"] == WEWN or not k["godziny_3m"]:
            continue
        if k["koszt_godziny"] and k["efektywna_stawka"] is not None:
            min_st = k["koszt_godziny"] / (1 - cel)
            if k["efektywna_stawka"] < min_st:
                gm = k["godziny_3m"] / mies
                add(1 if k["marza_3m"] < 0 else 2, f"Stawka u klienta {k['klient']} poniżej celu marży",
                    f"Efektywna stawka {k['efektywna_stawka']:.0f} zł/h przy koszcie {k['koszt_godziny']:.0f} zł/h. "
                    f"Dla marży {cel:.0%} potrzeba min. {min_st:.0f} zł/h (≈{gm:.0f} h/mies.).",
                    (min_st - k["efektywna_stawka"]) * gm)
        if k["wykorzystanie_pakietu"] and k["wykorzystanie_pakietu"] > 1.1:
            gm = k["godziny_3m"] / mies
            nowy = max(gm * (stawka_ref or 0), gm * (k["koszt_godziny"] or 0) / (1 - cel))
            add(1, f"Ryczałt {k['klient']}: pakiet przekroczony ({k['wykorzystanie_pakietu']:.0%})",
                f"Średnio {gm:.0f} h/mies. przy pakiecie {k['pakiet_3m'] / mies:.0f} h. Propozycja: ryczałt ok. {_zl(nowy)} "
                f"albo dopłata za nadgodziny.", nowy - (k["ryczalt"] or 0))
        elif k["wykorzystanie_pakietu"] is not None and k["wykorzystanie_pakietu"] < 0.5:
            add(3, f"Ryczałt {k['klient']}: niskie wykorzystanie ({k['wykorzystanie_pakietu']:.0%})",
                "Wysoka marża, ale ryzyko rezygnacji — warto pokazać klientowi wartość lub zaproponować inny zakres.")
    for n in w["naleznosci"]["klienci"]:
        if n["zalegle"] > 100:
            add(1, f"Zaległa płatność: {n['klient']}", f"Brakuje ok. {_zl(n['zalegle'])} brutto wpływów względem wykonanej pracy i terminu płatności. "
                "Sprawdź, czy faktury zostały wystawione i wyślij przypomnienie.")
    prev = [x for x in okno if x != m]
    for kat, v in M[m]["koszty_inne"].items():
        sr = _sr([M[x]["koszty_inne"].get(kat, 0) for x in prev])
        if sr and v > sr * 1.15 and v - sr > 500:
            add(2, f"Wzrost kosztów: {kat}", f"{_zl(v)} vs średnio {_zl(sr)} w poprzednich miesiącach (+{v / sr - 1:.0%}).", v - sr)
    nk = M[m]["nieprzypisane_transakcje"]
    if nk:
        add(2, f"{len(nk)} transakcji bez kategorii/klienta", "Dodaj reguły w konfiguracja.json (reguly_kosztow / aliasy 'bank' klientów), "
            "inaczej analiza kosztów i należności jest niepełna.")
    for z in w["zespol"]:
        if z["obciazenie"] is not None and z["koszt_3m"] and z["obciazenie"] < 0.6:
            add(2, f"Niskie obciążenie: {z['osoba']}", f"Zarejestrowano {z['obciazenie']:.0%} normy godzin przy koszcie {_zl(z['koszt_3m'] / mies)}/mies. "
                "Albo brakuje wpisów w Clockify, albo jest wolna moc przerobowa do sprzedania.")
        if z["udzial_rozliczalnych"] is not None and z["godziny_3m"] > 20 and z["udzial_rozliczalnych"] < 0.7:
            add(3, f"Dużo godzin nierozliczalnych: {z['osoba']}", f"Tylko {z['udzial_rozliczalnych']:.0%} czasu jest rozliczalne.")
    przych = sum(k["przychod_3m"] for k in w["klienci"])
    top = max(w["klienci"], key=lambda k: k["przychod_3m"], default=None)
    if top and przych and top["przychod_3m"] / przych > 0.4:
        add(2, "Koncentracja przychodu", f"{top['klient']} to {top['przychod_3m'] / przych:.0%} przychodu z 3 mies. — utrata klienta zagroziłaby płynności.")
    for nazwa, prog in w["prognoza"].items():
        ujemne = next((r for r in prog if r["saldo"] < 0), None)
        if ujemne:
            add(1, f"Ryzyko płynności (scenariusz {nazwa})", f"Saldo spada poniżej zera w {ujemne['miesiac']}: {_zl(ujemne['saldo'])}.")
            break
    wyd = _sr([M[x]["wydatki"] for x in okno if M[x]["bank"]])
    if wyd and M[m]["saldo"] is not None:
        runway = M[m]["saldo"] / wyd
        if runway < 3:
            add(1 if runway < 1.5 else 2, "Niska poduszka finansowa", f"Saldo pokrywa {runway:.1f} mies. wydatków (rekomendowane min. 3).")
    if koszt_h and stawka_ref and stawka_ref < koszt_h / (1 - cel):
        add(2, "Cennik godzinowy poniżej progu", f"Średnia stawka {stawka_ref:.0f} zł/h, a dla marży {cel:.0%} przy koszcie {koszt_h:.0f} zł/h potrzeba {koszt_h / (1 - cel):.0f} zł/h.")
    return sorted(R, key=lambda r: (r["priorytet"], -(r["wplyw_mies_pln"] or 0)))
