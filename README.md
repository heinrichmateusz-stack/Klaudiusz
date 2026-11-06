# Dashboard finansowy + agent CFO

Dwie części:
1. **`index.html`** — dashboard w przeglądarce (bez instalacji): przychody godzinowe i ryczałtowe, koszty, rentowność klientów,
   wykorzystanie pakietów godzin, cashflow i prognoza.
2. **`cfo/`** — potok danych dla agenta CFO: wczytuje wyciągi bankowe, eksporty Clockify i koszty zespołu z księgowości
   do bazy SQLite, liczy wynik, należności, prognozę 6 mies. i rekomendacje, generuje miesięczny raport.
   Agent (Claude) postępuje wg [`CLAUDE.md`](CLAUDE.md) i dopisuje komentarz CFO z decyzjami do podjęcia.

## Szybki start
```bash
pip install -r requirements.txt
python -m cfo init          # tworzy dane/ i dane/konfiguracja.json (uzupełnij klientów i zespół)
# wrzuć pliki:
#   dane/wejscie/bank/              wyciągi CSV/XLSX (najlepiej) albo PDF
#   dane/wejscie/czas-pracy/        Clockify: Reports → Detailed → Export CSV/Excel
#   dane/wejscie/koszty-zespolu/    Excel z księgowości: osoba + całkowity koszt (+ miesiąc lub miesiąc w nazwie pliku)
python -m cfo przetworz     # → dane/raporty/RRRR-MM-raport-cfo.md, dane/wyniki/dashboard.json
```
Podgląd na fikcyjnych danych: `CFO_DANE=dane-demo python -m cfo demo && CFO_DANE=dane-demo python -m cfo przetworz`.

Dashboard z danymi agenta: `python -m http.server` w katalogu repo → `http://localhost:8000` → Ustawienia →
„Wczytaj z bazy agenta CFO” (albo „Importuj kopię (JSON)” i wskaż `dane/wyniki/dashboard.json`).

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
`dane/` jest w `.gitignore`, bo repozytorium jest publiczne. Żeby agent miał dostęp do danych co miesiąc,
zmień repo na prywatne (albo trzymaj dane w osobnym prywatnym repo i ustaw `CFO_DANE`) i usuń `dane/` z `.gitignore`.
