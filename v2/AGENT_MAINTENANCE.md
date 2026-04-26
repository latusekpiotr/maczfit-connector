# Agent Maintenance Notes

Ten plik jest instrukcją do aktualizacji lokalnej bazy składników w `maczfit_pipeline.py`, gdy użytkownik prześle log terminala z brakującymi składnikami.

## Cel

Zmniejszać liczbę fallbacków w sekcji:

- `Missing ingredients using fallback nutrition profiles:`

## Gdzie edytować

W pliku:

- `maczfit_pipeline.py`

Sekcja do aktualizacji:

- `NUTRITION_DB`

## Jak pracować z logiem terminala

Log wypisuje wiersze w stylu:

```text
-   12.50% [API] Nazwa składnika | 2026-04-14 | Obiad | Nazwa dania
```

Znaczenie:

- procent to udział składnika w danym daniu,
- `[API]` oznacza, że procent pochodził wprost z danych Maczfit,
- `[estimated]` oznacza, że procent został oszacowany z pozostałej puli składników bez jawnego `%`.

Najpierw uzupełniaj składniki z najwyższym procentem, bo one najsilniej wpływają na wynik `sugars` i `saturated fatty acids`.

## Procedura aktualizacji bazy

1. Odczytaj z logu brakujące składniki, zaczynając od najwyższego procentu.
2. Dla każdego składnika sprawdź, jak skrypt go normalizuje:
   - małe litery,
   - usuwanie polskich znaków diakrytycznych,
   - zamiana `%` na spację,
   - uproszczenie interpunkcji do spacji.
3. Dodaj nowy wpis do `NUTRITION_DB` w formacie:

```python
("znormalizowana nazwa", {"kcal": 123, "sugars": 4.5, "sat": 1.2}),
```

4. Gdy istnieje ryzyko konfliktu z bardziej ogólną nazwą, wpis powinien być możliwie specyficzny. Przykład:
   - lepiej `("ser plesniowy typu blue", ...)`
   - niż samo `("ser", ...)`
5. Jeśli składnik jest wariantem znanego produktu, dobierz wartości z najbardziej zbliżonego odpowiednika i zanotuj rozsądne przybliżenie.
6. W `NUTRITION_DB` utrzymuj porządek alfabetyczny po znormalizowanym kluczu składnika. Nowe wpisy zawsze wstawiaj w odpowiednie miejsce zamiast dopisywać na końcu.
7. Po aktualizacji uruchom ponownie skrypt dla zakresu, z którego pochodził log, i sprawdź czy składnik zniknął z listy braków.

## Zasady doboru wpisów

- Preferuj konkretne wpisy przed ogólnymi.
- Nie usuwaj istniejących wpisów ogólnych, jeśli nadal są potrzebne jako fallback dopasowania.
- Jeżeli dwa wpisy są podobne, bardziej specyficzny powinien mieć dłuższy klucz tekstowy, bo matcher wybiera najdłuższe dopasowanie.
- Lista `NUTRITION_DB` powinna pozostać alfabetyczna, żeby łatwo było znaleźć duplikaty i brakujące miejsca.
- Jeśli nie ma wiarygodnych danych, lepiej dodać ostrożne przybliżenie niż zostawić ważny składnik na fallbacku ogólnym.

## Po zakończeniu

W odpowiedzi dla użytkownika podaj:

- które składniki zostały dopisane,
- czy po ponownym uruchomieniu lista braków się skróciła,
- czy pozostały jeszcze składniki wymagające ręcznego uzupełnienia.
