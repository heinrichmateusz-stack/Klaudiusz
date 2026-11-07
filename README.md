# Dashboard finansowy + agent CFO

Dwie części:
1. **`index.html`** — dashboard w przeglądarce (bez instalacji): przychody godzinowe i ryczałtowe, koszty, rentowność klientów,
   wykorzystanie pakietów godzin, cashflow i prognoza.
2. **`cfo/`** — potok danych dla agenta CFO: wczytuje wyciągi bankowe, eksporty Clockify i koszty zespołu z księgowości
   do bazy SQLite, liczy wynik, należności, prognozę 6 mies. i rekomendacje, generuje miesięczny raport.
   Agent (Claude) postępuje wg [`CLAUDE.md`](CLAUDE.md) i dopisuje komentarz CFO z decyzjami do podjęcia.

## Szybki start
Pełna instrukcja dla właściciela, asystentki i księgowej: **[INSTRUKCJA.md](INSTRUKCJA.md)**.
```bash
pip install -r requirements.txt
python -m cfo ustaw-folder "G:\Mój dysk\CFO"   # folder z danymi na Dysku Google (poza repozytorium)
python -m cfo zabezpiecz                         # blokada commitowania danych finansowych
# uzupełnij CFO/klienci.xlsx i wrzucaj pliki do CFO/wejscie/{bank,czas-pracy,koszty-zespolu}
python -m cfo przetworz                          # → CFO/raporty/RRRR-MM-raport-cfo.md, CFO/wyniki/dashboard.json
python -m cfo dashboard                          # dashboard z danymi, tylko na tym komputerze
```
Albo dwuklik `odswiez.bat` (Windows) / `odswiez.command` (Mac). Dane testowe: `CFO_DANE=/tmp/cfo-demo python -m cfo demo`.

## Co liczy
- **Wynik (netto, memoriałowo)**: godzinowi = godziny rozliczalne × stawka, ryczałtowi = kwota w miesiącach umowy;
  koszty = zespół (z księgowości, a gdy brak — z banku) + pozostałe koszty z wyciągu (bez VAT, wg kategorii).
- **Rentowność klientów**: koszt każdej osoby na godzinę × jej godziny u klienta + narzut kosztów ogólnych wg godzin.
- **Ryczałty**: wykorzystanie pakietu, efektywna stawka, propozycja nowej kwoty.
- **Należności**: przychód brutto po terminie płatności vs faktyczne wpływy od klienta (rozpoznawanego po aliasach).
- **Cashflow i prognoza 6 mies.**: scenariusz bazowy i ostrożny (−25% godzin, płatności o miesiąc później), z VAT i podatkiem.
- **Rekomendacje**: stawki poniżej docelowej marży, przekroczone pakiety, zaległości, wzrost kosztów, obciążenie zespołu,
  koncentracja przychodu, poduszka gotówkowa, nieskategoryzowane transakcje.

## Wyciągi PDF
PDF-y banków mają różne układy. Parser rozpoznaje typowy układ (data, opis, kwota, saldo) i **weryfikuje wynik saldami**.
Jeśli się nie zgadza, raport to oznacza, a agent odczytuje PDF i zapisuje obok plik CSV o tej samej nazwie (wtedy PDF jest pomijany).
Najpewniej działa eksport CSV z bankowości — jeśli bank go oferuje, wybierz go.

## Poufność
- Dane (wyciągi, godziny, koszty zespołu, raporty) leżą w folderze na Dysku Google, **poza repozytorium**. Git ich nie widzi.
- `cfo/straznik.py` blokuje commit i push plików CSV/Excel/PDF/baz, raportów i tekstów z numerami rachunków
  (hook `.githooks/pre-commit` + workflow `.github/workflows/blokada-danych.yml`). Fikcyjne przykłady trzymaj w `przyklady/`.
- Baza `finanse.db` jest lokalna (`~/.cfo/`), odtwarzalna z plików.
