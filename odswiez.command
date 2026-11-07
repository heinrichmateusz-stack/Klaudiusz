#!/bin/bash
# Odświeża dane z folderu CFO i otwiera dashboard (dwuklik w Finderze)
cd "$(dirname "$0")" || exit 1
if ! python3 -m cfo przetworz; then
  read -r -p "Wystąpił błąd — sprawdź komunikat powyżej. Enter zamyka okno."
  exit 1
fi
python3 -m cfo dashboard
