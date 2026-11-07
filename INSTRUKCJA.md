# Instrukcja: Dashboard finansowy CFO

Instrukcja dla właściciela, asystentki i księgowej. Dane leżą **tylko w folderze na Dysku Google**.
Program działa **lokalnie na komputerze** i nigdzie ich nie wysyła.

## Kto co robi

| Osoba | Potrzebuje | Zadanie |
|---|---|---|
| **Asystentka** | dostępu do folderu `CFO` na Dysku Google | co miesiąc wgrywa wyciąg z banku i eksport z Clockify; aktualizuje arkusz `klienci.xlsx` |
| **Księgowa** | dostępu **tylko** do podfolderu `koszty-zespolu` | co miesiąc wgrywa zestawienie kosztów zespołu |
| **Właściciel** | folderu `CFO` + programu na swoim komputerze | odświeża dane i przegląda dashboard oraz raport |

Asystentka i księgowa **nie muszą niczego instalować**. Korzystają tylko z Dysku Google w przeglądarce.

---

## 1. Folder na Dysku Google (raz, właściciel)

1. Na Dysku Google utwórz folder **`CFO`** (najlepiej w „Mój dysk”).
2. Program sam utworzy w nim strukturę (krok 3). Docelowo wygląda tak:
   ```
   CFO/
     klienci.xlsx              ← klienci, stawki, ryczałty, zespół (edytuje asystentka)
     wejscie/
       bank/                   ← wyciągi z banku
       czas-pracy/             ← eksporty z Clockify
       koszty-zespolu/         ← zestawienia od księgowej
     raporty/                  ← miesięczne raporty CFO (tworzy program)
     wyniki/                   ← dane do dashboardu (tworzy program)
   ```
3. **Udostępnianie** (prawy przycisk → Udostępnij):
   - folder `CFO` → asystentka jako **Edytujący**;
   - **tylko** podfolder `CFO/wejscie/koszty-zespolu` → księgowa jako **Edytujący**. Nie dawaj jej dostępu do całego `CFO`, jeśli nie musi widzieć wyciągów;
   - „Dostęp ogólny” zawsze ustaw na **„Ograniczony”**. Nigdy nie wybieraj „Każda osoba mająca link”.
4. Każda z osób powinna mieć włączoną **weryfikację dwuetapową** na koncie Google (myaccount.google.com → Bezpieczeństwo).

## 2. Instalacja programu (raz, tylko właściciel)

1. **Dysk Google na komputer**: zainstaluj „Dysk Google na komputer” (google.com/drive/download) i zaloguj się.
   Folder `CFO` pojawi się jako zwykły folder, np.:
   - Windows: `G:\Mój dysk\CFO`
   - Mac: `/Users/<Ty>/Library/CloudStorage/GoogleDrive-<twój e-mail>/Mój dysk/CFO`
2. **Python**: pobierz z python.org (wersja 3.11 lub nowsza). W Windows zaznacz w instalatorze **„Add python.exe to PATH”**.
3. **Program**: na stronie repozytorium na GitHubie kliknij **Code → Download ZIP** i rozpakuj, np. do `Dokumenty\CFO-program`.
   **Nie rozpakowuj programu na Dysk Google**: program i dane trzymamy osobno.
4. Otwórz terminal w folderze programu (Windows: w Eksploratorze wpisz `cmd` w pasku adresu; Mac: Terminal, `cd ` i przeciągnij folder) i wpisz:
   ```
   pip install -r requirements.txt
   python -m cfo ustaw-folder "G:\Mój dysk\CFO"
   ```
   (na Macu `python3` zamiast `python` i ścieżka z punktu 1). Program zapamięta folder i utworzy w nim strukturę oraz arkusz `klienci.xlsx`.

## 3. Arkusz `klienci.xlsx` (asystentka, na bieżąco)

Plik w folderze `CFO`. Otwieraj go w Excelu albo w Dysku Google przez „Otwórz w aplikacji”.
**Nie konwertuj go na Arkusz Google**, bo program czyta tylko pliki .xlsx.

- **Klienci**: jeden wiersz na klienta:
  - model `godzinowy` (wypełnij stawkę) albo `ryczałt` (kwota, pakiet godzin, miesiąc „od” w formacie `2026-01`);
  - termin płatności w dniach;
  - **Nazwy w banku**: fragmenty nazwy z przelewów, np. `alfa sp, 1234567890` (NIP). Po nich program rozpoznaje wpłaty;
  - **Nazwy w Clockify**: nazwa klienta lub projektu w Clockify.
- **Zespół**: imię i nazwisko jak w zestawieniu księgowej oraz inne nazwy tej osoby (z Clockify, przelewów).
- **Firma**: VAT, podatek, docelowa marża, godziny etatu.
- **Reguły kosztów**: fraza z opisu przelewu → kategoria (np. `coworking` → `Biuro`). Dopisuj, gdy raport pokaże „transakcje bez kategorii”.

Wiersze zaczynające się od `PRZYKŁAD` są pomijane. Możesz je usunąć.

## 4. Co miesiąc: wgrywanie danych (do 5. dnia następnego miesiąca)

**Asystentka**
1. **Bank** → `CFO/wejscie/bank/`. Eksportuj historię rachunku za poprzedni miesiąc **w formacie CSV**, bo jest najpewniejszy. Jeśli bank daje tylko PDF, wgraj PDF.
   Nazwa np. `bank-2026-10.csv`. Każdy miesiąc w osobnym pliku.
2. **Clockify** → `CFO/wejscie/czas-pracy/`: Reports → **Detailed** → zakres: poprzedni miesiąc → Export → CSV lub Excel.
   Nazwa np. `clockify-2026-10.csv`. **Nie wgrywaj dwa razy tego samego okresu**, bo godziny by się zdublowały.
   Poprawiony eksport zapisz pod tą samą nazwą, a stary usuń.

**Księgowa** → `CFO/wejscie/koszty-zespolu/`
- Excel z kolumnami **`Pracownik`** i **`Całkowity koszt pracodawcy`**. Dla współpracowników B2B wpisz kwotę netto faktury.
  Opcjonalnie `Forma współpracy`. Nazwa pliku z miesiącem: `koszty-zespolu-2026-10.xlsx`.

**Bezpieczny dostęp do banku dla asystentki**: nie przekazuj swojego loginu. W bankowości firmowej dodaj jej
osobnego użytkownika z uprawnieniem **tylko do podglądu / pobierania wyciągów** (bez zlecania przelewów).

## 5. Odświeżenie i dashboard (właściciel)

- **Windows**: dwuklik `odswiez.bat` w folderze programu. **Mac**: dwuklik `odswiez.command`
  (za pierwszym razem: prawy przycisk → Otwórz).
- Program wczyta nowe pliki, przeliczy wszystko i otworzy dashboard w przeglądarce.
  Dashboard jest dostępny **tylko na Twoim komputerze** (adres 127.0.0.1). Zamknij okno terminala, gdy skończysz.
- Raport miesięczny: `CFO/raporty/RRRR-MM-raport-cfo.md`. Zawiera wynik, rentowność klientów, zespół, należności, prognozę i rekomendacje.
  Sekcja **„8. Jakość danych”** pokazuje problemy z plikami: nierozpoznany PDF, przelewy bez kategorii, brak stawki klienta.

## 6. Komentarz CFO od Claude (opcjonalnie)

Raport z liczbami i rekomendacjami robi program, bez AI. Claude może dopisać komentarz z decyzjami do podjęcia
(procedura w `CLAUDE.md`). Pamiętaj, że wtedy **treść raportu i danych trafia do Anthropic** do przetworzenia.
Na GitHub nie trafia, ale opuszcza Twój komputer i Dysk Google. Sprawdź ustawienia prywatności swojego planu Claude.

## 7. Zabezpieczenia wbudowane w program

- Dane leżą poza folderem programu, więc git ich nie widzi i nie może ich wysłać na GitHub.
- **Blokada commitów**: po `python -m cfo zabezpiecz` każdy commit jest sprawdzany. Odrzucane są pliki CSV, Excel, PDF i bazy,
  pliki z raportami oraz teksty z numerami rachunków. Ta sama kontrola działa na GitHubie przy każdym wysłaniu zmian.
- Baza robocza (`finanse.db`) jest odtwarzana z plików i leży lokalnie w `~/.cfo/`, nie na Dysku Google.
  Dzięki temu nie ma konfliktów synchronizacji. Można ją w każdej chwili usunąć.
- Lokalny dashboard udostępnia wyłącznie stronę i plik z wynikami, tylko dla tego komputera.

## 8. Najczęstsze problemy

| Komunikat / objaw | Co zrobić |
|---|---|
| `python` nie jest rozpoznawany | Zainstaluj Pythona z zaznaczonym „Add to PATH” albo użyj `py` zamiast `python` |
| „Folder … nie istnieje” | Uruchom Dysk Google na komputer i sprawdź ścieżkę do `CFO` |
| ⚠️ PDF „uzgodnione: false” | Program nie odczytał poprawnie wyciągu PDF: wgraj CSV za ten miesiąc (PDF z CSV o tej samej nazwie jest pomijany) |
| „brak stawki godzinowej” | Uzupełnij stawkę klienta w `klienci.xlsx` |
| Klient z Clockify „brak w konfiguracji” | Dodaj klienta w `klienci.xlsx` lub jego nazwę z Clockify w kolumnie „Nazwy w Clockify” |
| Wpłata klienta jako „Wpływ nieprzypisany” | Dopisz fragment nazwy z przelewu w „Nazwy w banku” |
| Dashboard pusty | Najpierw musi się udać `python -m cfo przetworz`; potem `python -m cfo dashboard` |
