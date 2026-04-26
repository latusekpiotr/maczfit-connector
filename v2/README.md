# Maczfit Connector v2

`v2` pobiera menu Maczfit Smart Start bezpośrednio z publicznego API, filtruje je po podanym zakresie dat, a następnie od razu wzbogaca wynik o:

- `sugars`
- `saturated fatty acids`

W tej wersji użytkownik podaje tylko daty. Skrypt nie korzysta z fallbacku "same nazwy dań z DOM", więc do wyniku trafiają wyłącznie dni, które są faktycznie dostępne w API razem ze składnikami.

## Wymagania

- Python 3.10+.
- Dostęp do sieci do `https://www.maczfit.pl/api/v2/meals/diet/16`.

Skrypt używa wyłącznie standardowej biblioteki Pythona, więc nie trzeba nic doinstalowywać.

## Uruchomienie

Z katalogu `v2`:

```bash
python maczfit_pipeline.py 2026-04-14 2026-04-16
```

Możesz też podać pojedynczy dzień:

```bash
python maczfit_pipeline.py 2026-04-14
```

## Co zapisuje skrypt

Po każdym uruchomieniu skrypt zapisuje:

- `menu-output-enriched.json`

Plik zawiera:

- żądany zakres dat,
- listę dni, których nie było w API,
- `byDay` z menu i wzbogaconymi polami `sugars` oraz `saturated fatty acids`.

## Co wypisuje skrypt w terminalu

Po zakończeniu skrypt wypisuje:

- gdzie zapisał wynik,
- ile dni z zakresu udało się zapisać,
- które dni zostały pominięte, bo nie były dostępne w API,
- listę brakujących składników, dla których użyto fallbackowych profili żywieniowych.

Brakujące składniki są sortowane malejąco po oszacowanym udziale procentowym w pojedynczym daniu. Dzięki temu na górze listy widać te braki, które najbardziej wpływają na jakość enrichmentu.

## Ważne ograniczenie

Jeżeli danego dnia nie ma w odpowiedzi API, `v2` po prostu go pomija. To jest zachowanie celowe: brak składników oznacza, że enrichment byłby mało wiarygodny.

## Utrzymanie bazy składników

Jeżeli w terminalu pojawią się brakujące składniki, instrukcja aktualizacji bazy znajduje się w:

- `AGENT_MAINTENANCE.md`
