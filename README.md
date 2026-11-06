# Dashboard finansowy

Prosta aplikacja (jeden plik `index.html`, bez instalacji i serwera) do śledzenia, jak godziny pracy dla klientów
godzinowych i ryczałtowych oraz koszty miesięczne przekładają się na **przychody, rentowność i cashflow**.

## Uruchomienie
Otwórz `index.html` w przeglądarce (dwuklik). Dane zapisują się lokalnie w przeglądarce (localStorage) —
w zakładce *Ustawienia* zrób eksport kopii JSON. Wykresy wymagają internetu (Chart.js z CDN).

Na start kliknij **„Wczytaj dane demo”**, żeby zobaczyć przykład.

## Co liczy
- **Przychód**: klienci godzinowi = godziny × stawka; ryczałtowi = stała kwota w miesiącach trwania umowy.
- **Rentowność klienta**: koszty firmy rozkładane na klientów proporcjonalnie do godzin
  (lub wg stałej stawki wewnętrznej), efektywna stawka = przychód / godziny.
- **Ryczałty**: wykorzystanie pakietu godzin, efektywna stawka i wartość nadgodzin „oddanych” w ryczałcie.
- **Cashflow**: faktura na koniec miesiąca pracy, wpływ po terminie płatności klienta (1–30 dni → kolejny miesiąc),
  koszty w miesiącu poniesienia, podatek dochodowy (opcjonalny) w miesiącu następnym. Saldo + prognoza na kolejne miesiące.
- **Wnioski**: automatyczne alerty (klient poniżej kosztu godziny, przekroczony pakiet, ujemne saldo, koncentracja przychodu).

## Import godzin (CSV)
Kolumny: `data`, `klient`, `godziny` (`1,5` albo `1:30`), opcjonalnie `osoba`, `opis`. Separator `;`, `,` lub tab.
Rozpoznaje też eksporty Toggl/Clockify. Jeśli plik od klienta nie ma kolumny „klient”, wybierz klienta przy imporcie.
Przykład: `przyklad-godziny.csv`. Każdy import można cofnąć.

Wszystkie kwoty są netto (bez VAT).
