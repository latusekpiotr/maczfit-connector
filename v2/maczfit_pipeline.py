import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "menu-output-enriched.json"
DIET_MEALS_API = "https://www.maczfit.pl/api/v2/meals/diet/16"

# Fixed per-meal calorie targets come from the SmartStart diet assumptions
# provided by the user: sniadanie 400 kcal, drugie sniadanie 300 kcal,
# obiad 550 kcal, podwieczorek 350 kcal, kolacja 400 kcal.
MEAL_KCAL = {
    "sniadanie": 400,
    "ii sniadanie": 300,
    "obiad": 550,
    "podwieczorek": 350,
    "kolacja": 400,
}

PORTION_LIMITS = {
    "sniadanie": (250, 380),
    "ii sniadanie": (180, 320),
    "obiad": (350, 500),
    "podwieczorek": (180, 350),
    "kolacja": (250, 420),
}

MEALS = [
    "Śniadanie",
    "II śniadanie",
    "Obiad",
    "Podwieczorek",
    "Kolacja",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    text = text.translate(str.maketrans({
        "ł": "l",
        "Ł": "L",
    }))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("%", " ")
    text = re.sub(r"[.,;:/-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_ingredients(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<!\d),(?!\d)", text) if part.strip()]


def parse_ingredient(token: str) -> tuple[str, float | None]:
    match = re.match(r"^(.*?)\s*\((\d+(?:[.,]\d+)?)%\)\s*$", token.strip())
    if match:
        return match.group(1).strip(), float(match.group(2).replace(",", "."))
    return token.strip(), None


NUTRITION_DB = [
    ("ajwar", {"kcal": 90, "sugars": 6.0, "sat": 0.2}),
    ("ananas", {"kcal": 50, "sugars": 9.9, "sat": 0.0}),
    ("baklazan", {"kcal": 25, "sugars": 3.5, "sat": 0.0}),
    ("banan", {"kcal": 89, "sugars": 12.2, "sat": 0.1}),
    ("barszcz czerwony", {"kcal": 30, "sugars": 4.0, "sat": 0.1}),
    ("batat", {"kcal": 86, "sugars": 4.2, "sat": 0.0}),
    ("bazylia", {"kcal": 23, "sugars": 0.3, "sat": 0.0}),
    ("boczek pieczony", {"kcal": 541, "sugars": 1.0, "sat": 16.0}),
    ("brokuly", {"kcal": 35, "sugars": 1.7, "sat": 0.1}),
    ("brukselka", {"kcal": 43, "sugars": 2.2, "sat": 0.1}),
    ("brzoskwinia", {"kcal": 39, "sugars": 8.4, "sat": 0.0}),
    ("budyn w proszku o smaku czekoladowym", {"kcal": 360, "sugars": 75.0, "sat": 1.5}),
    ("budyn w proszku o smaku waniliowym", {"kcal": 350, "sugars": 80.0, "sat": 0.2}),
    ("bulka dyniowa", {"kcal": 270, "sugars": 4.0, "sat": 0.5}),
    ("bulka orkiszowa", {"kcal": 265, "sugars": 3.5, "sat": 0.5}),
    ("bulka rustykalna", {"kcal": 270, "sugars": 2.8, "sat": 0.6}),
    ("bulka tarta", {"kcal": 395, "sugars": 5.0, "sat": 0.7}),
    ("burak", {"kcal": 43, "sugars": 6.8, "sat": 0.0}),
    ("cebula", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("cebula czerwona", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("cebula duszona", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("cebula suszona", {"kcal": 349, "sugars": 38.0, "sat": 0.1}),
    ("chleb tostowy pelnoziarnisty", {"kcal": 255, "sugars": 6.0, "sat": 0.7}),
    ("chleb zytni", {"kcal": 230, "sugars": 3.8, "sat": 0.3}),
    ("chleb zytni dyniowy", {"kcal": 240, "sugars": 5.0, "sat": 0.3}),
    ("chleb zytni razowy", {"kcal": 230, "sugars": 3.8, "sat": 0.3}),
    ("chleb zytni ze slonecznikiem", {"kcal": 250, "sugars": 4.0, "sat": 0.4}),
    ("chipsy bananowe", {"kcal": 519, "sugars": 35.0, "sat": 29.0}),
    ("ciabatta pszenna z suszonymi pomidorami", {"kcal": 270, "sugars": 2.5, "sat": 0.7}),
    ("ciasto francuskie", {"kcal": 430, "sugars": 3.5, "sat": 10.0}),
    ("ciasto na pizze", {"kcal": 270, "sugars": 3.0, "sat": 1.0}),
    ("ciecierzyca", {"kcal": 164, "sugars": 4.8, "sat": 0.3}),
    ("cukier", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("cukier puder", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("cukier wanilinowy", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("cukinia", {"kcal": 17, "sugars": 2.5, "sat": 0.1}),
    ("cytryna", {"kcal": 29, "sugars": 2.5, "sat": 0.0}),
    ("cynamon", {"kcal": 247, "sugars": 2.2, "sat": 0.3}),
    ("czarnuszka", {"kcal": 375, "sugars": 0.3, "sat": 1.5}),
    ("czekolada biala", {"kcal": 539, "sugars": 59.0, "sat": 20.0}),
    ("czekolada gorzka", {"kcal": 546, "sugars": 24.0, "sat": 19.0}),
    ("czosnek", {"kcal": 149, "sugars": 1.0, "sat": 0.1}),
    ("daktyle suszone", {"kcal": 282, "sugars": 63.0, "sat": 0.0}),
    ("drozdze", {"kcal": 325, "sugars": 8.0, "sat": 1.5}),
    ("dynia", {"kcal": 26, "sugars": 2.8, "sat": 0.1}),
    ("estragon", {"kcal": 295, "sugars": 7.2, "sat": 1.9}),
    ("fasola biala", {"kcal": 140, "sugars": 0.3, "sat": 0.1}),
    ("fasola czarna", {"kcal": 132, "sugars": 0.3, "sat": 0.1}),
    ("fasola czerwona", {"kcal": 127, "sugars": 0.3, "sat": 0.1}),
    ("fasolka szparagowa zielona", {"kcal": 31, "sugars": 3.3, "sat": 0.1}),
    ("filet z dorsza czarnego", {"kcal": 180, "sugars": 0.0, "sat": 1.4}),
    ("filet z lososia", {"kcal": 208, "sugars": 0.0, "sat": 3.1}),
    ("filet z piersi indyka", {"kcal": 114, "sugars": 0.0, "sat": 0.4}),
    ("filet z piersi kurczaka", {"kcal": 165, "sugars": 0.0, "sat": 1.0}),
    ("galaretka truskawkowa", {"kcal": 330, "sugars": 80.0, "sat": 0.0}),
    ("galka muszkatolowa", {"kcal": 525, "sugars": 3.0, "sat": 25.9}),
    ("garam masala", {"kcal": 300, "sugars": 2.0, "sat": 0.8}),
    ("glony wakame", {"kcal": 45, "sugars": 0.5, "sat": 0.1}),
    ("gnocchi dyniowe", {"kcal": 160, "sugars": 2.0, "sat": 0.4}),
    ("granat", {"kcal": 83, "sugars": 13.7, "sat": 0.1}),
    ("granulat sojowy", {"kcal": 330, "sugars": 7.0, "sat": 0.7}),
    ("groszek zielony", {"kcal": 81, "sugars": 5.7, "sat": 0.1}),
    ("gruszka", {"kcal": 57, "sugars": 9.8, "sat": 0.0}),
    ("herbatniki kakowe bez cukru", {"kcal": 430, "sugars": 4.0, "sat": 4.0}),
    ("herbatniki waniliowe bez cukru", {"kcal": 430, "sugars": 3.0, "sat": 4.0}),
    ("imbir", {"kcal": 80, "sugars": 1.7, "sat": 0.2}),
    ("imbir mielony", {"kcal": 335, "sugars": 3.4, "sat": 2.6}),
    ("jablka", {"kcal": 52, "sugars": 10.4, "sat": 0.0}),
    ("jablko", {"kcal": 52, "sugars": 10.4, "sat": 0.0}),
    ("jagody goji", {"kcal": 349, "sugars": 45.0, "sat": 0.4}),
    ("jaja", {"kcal": 143, "sugars": 0.7, "sat": 3.3}),
    ("jogurt naturalny", {"kcal": 60, "sugars": 4.7, "sat": 1.0}),
    ("jogurt naturalny typu greckiego", {"kcal": 97, "sugars": 3.6, "sat": 4.8}),
    ("jogurt naturalny wysokobialkowy", {"kcal": 60, "sugars": 4.0, "sat": 0.3}),
    ("jogurt naturalny wysokobialkowy bez laktozy", {"kcal": 60, "sugars": 4.0, "sat": 0.3}),
    ("jogurt typu balkanskiego light", {"kcal": 65, "sugars": 4.0, "sat": 1.0}),
    ("kakao o obnizonej zawartosci tluszczu", {"kcal": 230, "sugars": 1.8, "sat": 8.0}),
    ("kapary w zalewie", {"kcal": 23, "sugars": 0.4, "sat": 0.2}),
    ("kapusta biala", {"kcal": 25, "sugars": 3.2, "sat": 0.0}),
    ("kapusta kiszona", {"kcal": 19, "sugars": 1.8, "sat": 0.0}),
    ("kapusta pekinska", {"kcal": 16, "sugars": 1.4, "sat": 0.0}),
    ("kardamon", {"kcal": 311, "sugars": 0.0, "sat": 0.7}),
    ("kasza bulgur", {"kcal": 83, "sugars": 0.1, "sat": 0.0}),
    ("kasza jaglana ekspandowana", {"kcal": 380, "sugars": 1.0, "sat": 0.7}),
    ("kasza jeczmienna peczak", {"kcal": 123, "sugars": 0.5, "sat": 0.2}),
    ("kasza kuskus", {"kcal": 112, "sugars": 0.1, "sat": 0.0}),
    ("kasza manna", {"kcal": 360, "sugars": 0.4, "sat": 0.2}),
    ("kawa rozpuszczalna", {"kcal": 350, "sugars": 2.0, "sat": 0.2}),
    ("ketchup", {"kcal": 112, "sugars": 22.0, "sat": 0.0}),
    ("kielbasa krakowska", {"kcal": 300, "sugars": 1.0, "sat": 11.0}),
    ("kielbasa z kurczaka", {"kcal": 220, "sugars": 1.0, "sat": 6.0}),
    ("kielki fasoli mung", {"kcal": 30, "sugars": 4.1, "sat": 0.0}),
    ("kluski leniwe", {"kcal": 170, "sugars": 3.0, "sat": 1.8}),
    ("kmin rzymski", {"kcal": 375, "sugars": 2.3, "sat": 1.5}),
    ("kminek", {"kcal": 333, "sugars": 7.0, "sat": 0.6}),
    ("kolendra", {"kcal": 23, "sugars": 0.9, "sat": 0.0}),
    ("koncentrat bialek serwatkowych", {"kcal": 380, "sugars": 8.0, "sat": 5.0}),
    ("koncentrat pomidorowy", {"kcal": 82, "sugars": 12.0, "sat": 0.0}),
    ("konfitura zurawinowa", {"kcal": 220, "sugars": 52.0, "sat": 0.0}),
    ("koperek", {"kcal": 43, "sugars": 0.0, "sat": 0.1}),
    ("korzen pietruszki", {"kcal": 55, "sugars": 4.8, "sat": 0.1}),
    ("kotleciki warzywne z grzybami", {"kcal": 170, "sugars": 3.0, "sat": 0.8}),
    ("kopytka", {"kcal": 150, "sugars": 1.5, "sat": 0.2}),
    ("ksylitol", {"kcal": 240, "sugars": 0.0, "sat": 0.0}),
    ("kukurydza", {"kcal": 96, "sugars": 6.3, "sat": 0.2}),
    ("kukurydza konserwowa", {"kcal": 96, "sugars": 4.5, "sat": 0.2}),
    ("kurkuma", {"kcal": 312, "sugars": 3.2, "sat": 3.1}),
    ("lisc laurowy", {"kcal": 313, "sugars": 0.0, "sat": 2.3}),
    ("lopatka wieprzowa", {"kcal": 242, "sugars": 0.0, "sat": 7.5}),
    ("lubczyk", {"kcal": 20, "sugars": 3.0, "sat": 0.1}),
    ("majeranek", {"kcal": 270, "sugars": 4.1, "sat": 2.4}),
    ("majonez light", {"kcal": 270, "sugars": 2.0, "sat": 2.0}),
    ("majonez weganski", {"kcal": 300, "sugars": 1.0, "sat": 2.0}),
    ("mak niebieski", {"kcal": 525, "sugars": 2.7, "sat": 4.5}),
    ("maka bezglutenowa", {"kcal": 360, "sugars": 1.0, "sat": 0.3}),
    ("maka bezglutenowa mix", {"kcal": 360, "sugars": 2.0, "sat": 0.3}),
    ("maka owsiana", {"kcal": 404, "sugars": 1.2, "sat": 1.4}),
    ("maka pszenna", {"kcal": 364, "sugars": 0.3, "sat": 0.2}),
    ("maka pszenna pelnoziarnista", {"kcal": 340, "sugars": 0.4, "sat": 0.2}),
    ("makaron chow mein", {"kcal": 170, "sugars": 1.0, "sat": 0.3}),
    ("makaron pelnoziarnisty pszenny", {"kcal": 149, "sugars": 0.8, "sat": 0.3}),
    ("makaron pszenny", {"kcal": 158, "sugars": 0.6, "sat": 0.2}),
    ("makaron ryzowy", {"kcal": 109, "sugars": 0.2, "sat": 0.1}),
    ("makaron spaghetti pszenny", {"kcal": 158, "sugars": 0.6, "sat": 0.2}),
    ("makaron tagliatelle pomidorowe", {"kcal": 160, "sugars": 2.0, "sat": 0.3}),
    ("makaron z manioku", {"kcal": 160, "sugars": 1.0, "sat": 0.1}),
    ("maliny", {"kcal": 52, "sugars": 4.4, "sat": 0.0}),
    ("mango", {"kcal": 60, "sugars": 13.7, "sat": 0.1}),
    ("marchew", {"kcal": 41, "sugars": 4.7, "sat": 0.0}),
    ("marynowana rzodkiew zolta", {"kcal": 25, "sugars": 4.0, "sat": 0.0}),
    ("maslo", {"kcal": 717, "sugars": 0.1, "sat": 51.0}),
    ("mieso drobne z indyka", {"kcal": 150, "sugars": 0.0, "sat": 2.0}),
    ("mieso mielone z kurczaka", {"kcal": 170, "sugars": 0.0, "sat": 3.0}),
    ("migdal platki", {"kcal": 579, "sugars": 4.4, "sat": 3.8}),
    ("migdaly", {"kcal": 579, "sugars": 4.4, "sat": 3.8}),
    ("mini pumpernikiel", {"kcal": 250, "sugars": 6.0, "sat": 0.2}),
    ("mieszanka grzybow lesnych", {"kcal": 35, "sugars": 2.5, "sat": 0.1}),
    ("mieszanka warzyw suszonych", {"kcal": 240, "sugars": 20.0, "sat": 0.3}),
    ("miod pszczeli", {"kcal": 304, "sugars": 82.0, "sat": 0.0}),
    ("mleko 0 5 tl", {"kcal": 37, "sugars": 5.1, "sat": 0.3}),
    ("mleko bez laktozy 1 5 tl", {"kcal": 46, "sugars": 5.0, "sat": 1.0}),
    ("mleko kokosowe", {"kcal": 180, "sugars": 2.0, "sat": 16.0}),
    ("mleko sojowe", {"kcal": 33, "sugars": 2.5, "sat": 0.5}),
    ("mix salat", {"kcal": 17, "sugars": 2.0, "sat": 0.0}),
    ("morele", {"kcal": 48, "sugars": 9.2, "sat": 0.0}),
    ("mozzarella", {"kcal": 254, "sugars": 1.0, "sat": 13.0}),
    ("mozzarella light", {"kcal": 170, "sugars": 1.0, "sat": 8.0}),
    ("mozzarella mini", {"kcal": 250, "sugars": 1.0, "sat": 11.0}),
    ("mus mango", {"kcal": 65, "sugars": 14.0, "sat": 0.1}),
    ("musztarda", {"kcal": 140, "sugars": 6.0, "sat": 0.3}),
    ("musztarda sarepska", {"kcal": 140, "sugars": 6.0, "sat": 0.3}),
    ("nachosy kukurydziane", {"kcal": 490, "sugars": 1.0, "sat": 1.1}),
    ("natka pietruszki", {"kcal": 36, "sugars": 0.9, "sat": 0.1}),
    ("ocet balsamiczny", {"kcal": 88, "sugars": 15.0, "sat": 0.0}),
    ("ocet ryzowy", {"kcal": 20, "sugars": 0.1, "sat": 0.0}),
    ("ocet winny bialy", {"kcal": 19, "sugars": 0.1, "sat": 0.0}),
    ("ogorek", {"kcal": 15, "sugars": 1.7, "sat": 0.0}),
    ("ogorek kiszony", {"kcal": 11, "sugars": 1.1, "sat": 0.0}),
    ("olej rzepakowy", {"kcal": 884, "sugars": 0.0, "sat": 7.0}),
    ("olej sezamowy", {"kcal": 884, "sugars": 0.0, "sat": 14.0}),
    ("oliwa z oliwek", {"kcal": 884, "sugars": 0.0, "sat": 14.0}),
    ("oliwki czarne", {"kcal": 115, "sugars": 0.0, "sat": 2.3}),
    ("oliwki zielone", {"kcal": 145, "sugars": 0.5, "sat": 2.0}),
    ("oregano", {"kcal": 260, "sugars": 4.0, "sat": 2.0}),
    ("orzechy arachidowe prazone w karmelu", {"kcal": 550, "sugars": 24.0, "sat": 8.0}),
    ("orzechy laskowe", {"kcal": 628, "sugars": 4.3, "sat": 4.5}),
    ("orzechy nerkowca", {"kcal": 553, "sugars": 5.9, "sat": 7.8}),
    ("orzechy wloskie", {"kcal": 654, "sugars": 2.6, "sat": 6.1}),
    ("orzeszki arachidowe", {"kcal": 585, "sugars": 4.7, "sat": 6.8}),
    ("orzeszki ziemne prazone", {"kcal": 585, "sugars": 4.7, "sat": 6.8}),
    ("owoce lesne", {"kcal": 50, "sugars": 7.0, "sat": 0.1}),
    ("paluchy bezglutenowe z suszonymi pomidorami", {"kcal": 410, "sugars": 5.0, "sat": 1.0}),
    ("paluchy z ziolami", {"kcal": 390, "sugars": 4.0, "sat": 1.5}),
    ("pancakes mini", {"kcal": 227, "sugars": 11.0, "sat": 2.0}),
    ("papryka", {"kcal": 31, "sugars": 4.2, "sat": 0.0}),
    ("papryka czerwona", {"kcal": 31, "sugars": 4.2, "sat": 0.0}),
    ("papryka czerwona mielona ostra", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("papryka mielona gochugaru", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("papryka slodka mielona", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("pasta curry zolta", {"kcal": 140, "sugars": 6.0, "sat": 2.0}),
    ("pasta harrisa", {"kcal": 120, "sugars": 6.0, "sat": 0.6}),
    ("pasta miso jasna", {"kcal": 199, "sugars": 6.2, "sat": 1.0}),
    ("pasta sezamowa tahini", {"kcal": 595, "sugars": 1.6, "sat": 7.0}),
    ("pasta z orzechow nerkowca", {"kcal": 587, "sugars": 5.9, "sat": 10.5}),
    ("pektyna", {"kcal": 325, "sugars": 0.0, "sat": 0.0}),
    ("pestki dyni", {"kcal": 559, "sugars": 1.4, "sat": 8.7}),
    ("pieczywo chrupkie bezglutenowe", {"kcal": 380, "sugars": 3.5, "sat": 0.8}),
    ("pieczarka", {"kcal": 22, "sugars": 2.0, "sat": 0.0}),
    ("pieprz bialy", {"kcal": 296, "sugars": 0.6, "sat": 0.6}),
    ("pieprz czarny", {"kcal": 250, "sugars": 0.6, "sat": 1.4}),
    ("pieprz cytrynowy", {"kcal": 250, "sugars": 3.0, "sat": 0.5}),
    ("pieprz ziolowy", {"kcal": 260, "sugars": 5.0, "sat": 0.8}),
    ("pierogi ruskie z tofu", {"kcal": 170, "sugars": 2.0, "sat": 1.0}),
    ("pierozki gyoza z warzywami", {"kcal": 190, "sugars": 4.0, "sat": 0.8}),
    ("pietruszka korzen", {"kcal": 55, "sugars": 4.8, "sat": 0.1}),
    ("platki drozdzowe nieaktywne", {"kcal": 350, "sugars": 12.0, "sat": 5.0}),
    ("platki jaglane", {"kcal": 378, "sugars": 0.4, "sat": 0.7}),
    ("platki owsiane bezglutenowe", {"kcal": 379, "sugars": 1.0, "sat": 1.2}),
    ("platki owsiane gorskie", {"kcal": 379, "sugars": 1.0, "sat": 1.2}),
    ("platki suszonej papryki", {"kcal": 282, "sugars": 10.0, "sat": 0.5}),
    ("platki zytnie", {"kcal": 335, "sugars": 1.2, "sat": 0.3}),
    ("pomarancza", {"kcal": 47, "sugars": 9.4, "sat": 0.0}),
    ("pomidor czerwony", {"kcal": 18, "sugars": 2.6, "sat": 0.0}),
    ("pomidor daktylowy", {"kcal": 18, "sugars": 2.7, "sat": 0.0}),
    ("pomidor daktylowy czerwony", {"kcal": 18, "sugars": 2.6, "sat": 0.0}),
    ("pomidory krojone", {"kcal": 21, "sugars": 3.9, "sat": 0.0}),
    ("pomidory suszone w oleju", {"kcal": 213, "sugars": 12.4, "sat": 1.5}),
    ("por", {"kcal": 61, "sugars": 3.9, "sat": 0.0}),
    ("porzeczka czerwona", {"kcal": 56, "sugars": 7.4, "sat": 0.0}),
    ("posypka bruschetta", {"kcal": 300, "sugars": 12.0, "sat": 1.0}),
    ("pesto czerwone", {"kcal": 460, "sugars": 6.0, "sat": 3.5}),
    ("pesto zielone", {"kcal": 450, "sugars": 4.0, "sat": 4.0}),
    ("proszek do pieczenia", {"kcal": 53, "sugars": 0.0, "sat": 0.0}),
    ("przyprawa curry", {"kcal": 325, "sugars": 2.0, "sat": 2.2}),
    ("przyprawa do piernika", {"kcal": 250, "sugars": 5.0, "sat": 0.5}),
    ("puder buraczany", {"kcal": 350, "sugars": 60.0, "sat": 0.2}),
    ("pulpa z marakui", {"kcal": 97, "sugars": 11.2, "sat": 0.7}),
    ("puree wisniowe", {"kcal": 50, "sugars": 10.0, "sat": 0.1}),
    ("rabarbar", {"kcal": 21, "sugars": 1.1, "sat": 0.0}),
    ("ricotta", {"kcal": 174, "sugars": 3.0, "sat": 10.9}),
    ("rodzynki", {"kcal": 299, "sugars": 59.0, "sat": 0.1}),
    ("roszponka", {"kcal": 21, "sugars": 0.7, "sat": 0.0}),
    ("rukola", {"kcal": 25, "sugars": 2.1, "sat": 0.1}),
    ("ryz basmati", {"kcal": 130, "sugars": 0.1, "sat": 0.0}),
    ("ryz do risotto arborio", {"kcal": 130, "sugars": 0.1, "sat": 0.1}),
    ("ryz jasminowy", {"kcal": 130, "sugars": 0.1, "sat": 0.0}),
    ("rzodkiewka", {"kcal": 16, "sugars": 1.9, "sat": 0.0}),
    ("sezam bialy", {"kcal": 573, "sugars": 0.3, "sat": 7.0}),
    ("sezam czarny", {"kcal": 573, "sugars": 0.3, "sat": 7.0}),
    ("seler korzen", {"kcal": 42, "sugars": 1.6, "sat": 0.1}),
    ("ser dojrzewajacy", {"kcal": 380, "sugars": 0.5, "sat": 21.0}),
    ("ser feta bez laktozy", {"kcal": 260, "sugars": 1.5, "sat": 14.0}),
    ("ser kozi", {"kcal": 320, "sugars": 0.5, "sat": 21.0}),
    ("ser owczy", {"kcal": 300, "sugars": 1.0, "sat": 18.0}),
    ("ser plesniowy typu blue", {"kcal": 353, "sugars": 0.5, "sat": 18.7}),
    ("ser podpuszczkowy", {"kcal": 350, "sugars": 1.0, "sat": 19.0}),
    ("ser twarogowy bez laktozy poltlusty", {"kcal": 133, "sugars": 3.5, "sat": 4.0}),
    ("ser twarogowy chudy", {"kcal": 99, "sugars": 3.4, "sat": 0.5}),
    ("ser typu feta", {"kcal": 260, "sugars": 1.5, "sat": 14.0}),
    ("ser typu halloumi", {"kcal": 321, "sugars": 2.7, "sat": 19.0}),
    ("ser weganski", {"kcal": 280, "sugars": 0.5, "sat": 20.0}),
    ("ser zolty", {"kcal": 350, "sugars": 1.0, "sat": 19.0}),
    ("ser zolty bez laktozy", {"kcal": 350, "sugars": 1.0, "sat": 19.0}),
    ("serek homogenizowany naturalny", {"kcal": 110, "sugars": 4.5, "sat": 3.0}),
    ("serek homogenizowany waniliowy", {"kcal": 160, "sugars": 13.0, "sat": 3.0}),
    ("serek naturalny bez laktozy", {"kcal": 90, "sugars": 4.0, "sat": 2.5}),
    ("serek naturalny light", {"kcal": 90, "sugars": 4.0, "sat": 2.5}),
    ("serek smietankowy naturalny", {"kcal": 250, "sugars": 4.0, "sat": 14.0}),
    ("serek wiejski", {"kcal": 98, "sugars": 2.7, "sat": 1.8}),
    ("siemie lniane", {"kcal": 534, "sugars": 1.6, "sat": 3.7}),
    ("skrobia ziemniaczana", {"kcal": 333, "sugars": 0.0, "sat": 0.0}),
    ("slonecznik", {"kcal": 584, "sugars": 2.6, "sat": 5.2}),
    ("sliwki", {"kcal": 46, "sugars": 10.0, "sat": 0.0}),
    ("smietana 12", {"kcal": 133, "sugars": 4.1, "sat": 7.6}),
    ("smietana 18", {"kcal": 193, "sugars": 3.6, "sat": 11.3}),
    ("smietana bez laktozy 18", {"kcal": 193, "sugars": 3.6, "sat": 11.3}),
    ("smietanka 12", {"kcal": 136, "sugars": 4.0, "sat": 7.7}),
    ("smietanka 30", {"kcal": 292, "sugars": 3.1, "sat": 19.0}),
    ("soda oczyszczona", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("soczewica czerwona", {"kcal": 116, "sugars": 1.8, "sat": 0.1}),
    ("soczewica zielona", {"kcal": 116, "sugars": 1.8, "sat": 0.1}),
    ("sol", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("sok pomaranczowy", {"kcal": 45, "sugars": 8.4, "sat": 0.0}),
    ("sok z cytryny", {"kcal": 22, "sugars": 2.5, "sat": 0.0}),
    ("sok z limonki", {"kcal": 25, "sugars": 1.7, "sat": 0.0}),
    ("sos hoisin", {"kcal": 220, "sugars": 48.0, "sat": 0.5}),
    ("sos pikantno slodki", {"kcal": 180, "sugars": 35.0, "sat": 0.0}),
    ("sos pomidorowy", {"kcal": 45, "sugars": 6.0, "sat": 0.0}),
    ("sos pomidorowy z ziolami", {"kcal": 45, "sugars": 6.0, "sat": 0.0}),
    ("sos rybny", {"kcal": 35, "sugars": 3.6, "sat": 0.0}),
    ("sos sojowy bezglutenowy", {"kcal": 53, "sugars": 4.9, "sat": 0.1}),
    ("sos sojowy jasny", {"kcal": 53, "sugars": 4.9, "sat": 0.1}),
    ("sos sriracha", {"kcal": 100, "sugars": 20.0, "sat": 0.0}),
    ("sos teriyaki", {"kcal": 89, "sugars": 15.0, "sat": 0.0}),
    ("sos worcester", {"kcal": 78, "sugars": 19.0, "sat": 0.0}),
    ("spod pelnoziarnisty", {"kcal": 265, "sugars": 3.0, "sat": 1.2}),
    ("szczypior", {"kcal": 30, "sugars": 1.9, "sat": 0.1}),
    ("szparagi biale mrozone", {"kcal": 20, "sugars": 1.8, "sat": 0.0}),
    ("szpinak", {"kcal": 23, "sugars": 0.4, "sat": 0.1}),
    ("tapioka", {"kcal": 130, "sugars": 0.0, "sat": 0.0}),
    ("tofu naturalne", {"kcal": 145, "sugars": 0.7, "sat": 1.0}),
    ("tofu wedzone", {"kcal": 170, "sugars": 1.6, "sat": 1.3}),
    ("tortellini ze szpinakiem i ricotta", {"kcal": 190, "sugars": 2.0, "sat": 2.2}),
    ("tortilla orkiszowo owsiana", {"kcal": 290, "sugars": 2.5, "sat": 1.5}),
    ("tortilla pszenna", {"kcal": 310, "sugars": 2.5, "sat": 1.3}),
    ("truskawki", {"kcal": 32, "sugars": 4.9, "sat": 0.0}),
    ("twarog sernikowy", {"kcal": 220, "sugars": 3.5, "sat": 9.0}),
    ("tymianek", {"kcal": 275, "sugars": 1.7, "sat": 2.7}),
    ("wafelki kukurydziane z nasionami konopi", {"kcal": 390, "sugars": 1.5, "sat": 0.9}),
    ("weganska smietana sojowa", {"kcal": 170, "sugars": 2.0, "sat": 1.6}),
    ("wiorki kokosowe", {"kcal": 660, "sugars": 7.0, "sat": 57.0}),
    ("winogrono ciemne", {"kcal": 69, "sugars": 15.5, "sat": 0.1}),
    ("witamina c", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("woda", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("ziele angielskie", {"kcal": 263, "sugars": 0.0, "sat": 6.0}),
    ("ziemniaki", {"kcal": 77, "sugars": 0.8, "sat": 0.0}),
    ("ziola prowansalskie", {"kcal": 260, "sugars": 4.0, "sat": 2.0}),
    ("zelatyna", {"kcal": 335, "sugars": 0.0, "sat": 0.0}),
    ("zoltko jaja", {"kcal": 322, "sugars": 0.6, "sat": 9.6}),
    ("zurawina", {"kcal": 46, "sugars": 4.3, "sat": 0.1}),
    ("zurawina suszona slodzona", {"kcal": 325, "sugars": 65.0, "sat": 0.1}),
]

GENERIC_DEFAULTS = [
    ("sok z cytryny", {"kcal": 22, "sugars": 2.5, "sat": 0.0}),
    ("ocet ryzowy", {"kcal": 20, "sugars": 0.1, "sat": 0.0}),
    ("garam masala", {"kcal": 300, "sugars": 2.0, "sat": 0.8}),
    ("cynamon", {"kcal": 247, "sugars": 2.2, "sat": 0.3}),
    ("galka muszkatolowa", {"kcal": 525, "sugars": 3.0, "sat": 25.9}),
    ("lisc laurowy", {"kcal": 313, "sugars": 0.0, "sat": 2.3}),
    ("ziele angielskie", {"kcal": 263, "sugars": 0.0, "sat": 6.0}),
    ("kminek", {"kcal": 333, "sugars": 7.0, "sat": 0.6}),
]

DESSERT_HINTS = [
    "owsianka",
    "sernik",
    "budyn",
    "muffinka",
    "pancakes",
    "nalesnik",
    "granola",
    "shake",
    "deser",
    "galaretka",
    "wanili",
    "czekolad",
    "rodzyn",
    "mus ",
]


def parse_cli_args() -> tuple[str, str]:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Maczfit Smart Start menu from the public API for the given date "
            "or inclusive date range, then enrich each dish with sugars and "
            "saturated fatty acids."
        )
    )
    parser.add_argument("start_date", help="Start date in YYYY-MM-DD format")
    parser.add_argument(
        "end_date",
        nargs="?",
        help="Optional end date in YYYY-MM-DD format (inclusive)",
    )
    args = parser.parse_args()
    start = args.start_date
    end = args.end_date or args.start_date
    start_dt = parse_iso_date(start)
    end_dt = parse_iso_date(end)
    if end_dt < start_dt:
        raise SystemExit(f"End date {end} is before start date {start}.")
    return start, end


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid ISO date: {value}. Expected YYYY-MM-DD.") from exc


def each_ymd_inclusive(start: str, end: str) -> list[str]:
    start_dt = parse_iso_date(start)
    end_dt = parse_iso_date(end)
    days = []
    current = start_dt
    while current <= end_dt:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def fetch_api_payload() -> dict:
    request = Request(
        DIET_MEALS_API,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.maczfit.pl/",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise SystemExit(f"Maczfit API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SystemExit(f"Could not reach Maczfit API: {exc.reason}") from exc
    return json.loads(body)


def build_by_meal_from_api_day(api_day: dict) -> list[dict]:
    by_meal = []
    for label in MEALS:
        rows = [item for item in api_day["meals"] if item["type"]["human"] == label]
        if len(rows) != 2:
            raise ValueError(
                f'API: expected 2 options for "{label}" on {api_day["date"]["value"]}, '
                f"got {len(rows)}"
            )
        by_meal.append(
            {
                "meal": label,
                "options": [
                    {
                        "name": item["name"].strip(),
                        "ingredients": normalize_ingredients(item.get("ingredients", "")),
                    }
                    for item in rows
                ],
            }
        )
    return by_meal


def normalize_ingredients(value: str) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def filter_requested_days(api_payload: dict, requested_days: list[str]) -> tuple[list[dict], list[str]]:
    requested = set(requested_days)
    api_days = api_payload.get("data", [])
    matched_days = [day for day in api_days if day.get("date", {}).get("value") in requested]
    matched_days.sort(key=lambda day: day["date"]["value"])
    available_days = {day["date"]["value"] for day in matched_days}
    missing_days = [ymd for ymd in requested_days if ymd not in available_days]
    return matched_days, missing_days


def fallback_profile(name: str) -> dict[str, float]:
    n = normalize(name)
    for key, values in GENERIC_DEFAULTS:
        if key in n:
            return values
    if any(word in n for word in ["sos", "pesto", "pasta "]):
        return {"kcal": 250, "sugars": 4.0, "sat": 2.0}
    if any(word in n for word in ["olej", "oliwa"]):
        return {"kcal": 884, "sugars": 0.0, "sat": 10.0}
    if any(word in n for word in ["ser", "serek", "ricotta", "twarog", "mozzarella"]):
        return {"kcal": 240, "sugars": 3.0, "sat": 12.0}
    if any(word in n for word in ["jogurt", "mleko", "smiet", "krem"]):
        return {"kcal": 90, "sugars": 4.5, "sat": 3.0}
    if any(word in n for word in ["chleb", "ciabatta", "pumpernikiel", "paluch", "herbatnik", "makaron", "maka", "ryz", "kasza", "platki", "pierogi", "tortellini", "pancakes", "nachosy"]):
        return {"kcal": 250, "sugars": 3.0, "sat": 1.0}
    if any(word in n for word in ["fasola", "ciecierzyca", "tofu", "soj", "kurczak", "indyk", "dorsz", "kielbasa", "jaja"]):
        return {"kcal": 160, "sugars": 1.0, "sat": 2.0}
    if any(word in n for word in ["orzech", "migdal", "sezam", "slonecznik", "pestki", "tahini", "kokos"]):
        return {"kcal": 580, "sugars": 3.0, "sat": 8.0}
    if any(word in n for word in ["gruszka", "jabl", "truskawk", "mango", "granat", "brzoskw", "morel", "porzeczk", "marakui", "pomarancz", "ananas", "wisni", "banan"]):
        return {"kcal": 55, "sugars": 10.0, "sat": 0.1}
    if any(word in n for word in ["papryka", "pomidor", "ogorek", "cukinia", "kalafior", "szpinak", "rukola", "salat", "kapusta", "marchew", "burak", "batat", "ziemniak", "dynia", "cebula", "pieczarka", "seler", "pietruszka", "groszek"]):
        return {"kcal": 30, "sugars": 3.0, "sat": 0.1}
    return {"kcal": 40, "sugars": 1.0, "sat": 0.1}


def lookup_profile(name: str) -> tuple[dict[str, float], str | None]:
    normalized = normalize(name)
    best_match = None
    best_key = None
    best_length = -1
    for key, values in NUTRITION_DB:
        if key in normalized and len(key) > best_length:
            best_match = values
            best_key = key
            best_length = len(key)
    if best_match is not None:
        return best_match, best_key
    return fallback_profile(name), None


def is_probably_sweet(option: dict) -> bool:
    haystack = normalize(f"{option['name']} {option['ingredients']}")
    return any(hint in haystack for hint in DESSERT_HINTS)


def implicit_weight(name: str, option: dict | None = None) -> float:
    n = normalize(name)
    sweet_option = is_probably_sweet(option) if option is not None else False

    if any(word in n for word in ["cukier", "miod"]):
        # In savory meals an unspecified sugar entry is usually a small balancing
        # addition, not a major ingredient, so keep its inferred share low.
        return 1.2 if sweet_option else 0.15

    if any(word in n for word in ["sol", "pieprz", "witamina", "lisc laurowy", "ziele angielskie", "oregano", "tymianek", "majeranek", "kolendra", "bazylia", "koperek", "natka", "szczypior", "cynamon", "galka", "kurkuma", "papryka", "kmin", "kminek", "imbir", "przyprawa", "proszek do pieczenia", "soda"]):
        return 0.2
    if any(word in n for word in ["czosnek", "sok z cytryny", "ocet", "sos sojowy", "sriracha", "harissa", "koncentrat", "budyn", "galaretka", "cukier wanilinowy", "zelatyna", "kielki"]):
        return 0.5
    if any(word in n for word in ["olej", "oliwa", "maslo", "majonez", "pesto", "tahini", "orzech", "slonecznik", "sezam", "pestki", "kokos", "chipsy", "zurawina", "goji", "czekolada", "ser dojrzewajacy", "ser zolty", "ser weganski"]):
        return 1.2
    if any(word in n for word in ["chleb", "ciabatta", "pumpernikiel", "paluch", "herbatniki", "maka", "ryz", "kasza", "makaron", "pierogi", "tortellini", "pancakes", "nachosy", "platki"]):
        return 1.0
    if any(word in n for word in ["ser", "serek", "ricotta", "twarog", "jogurt", "mleko", "smiet", "jaja", "tofu", "kurczak", "indyk", "dorsz", "kielbasa", "fasola", "ciecierzyca"]):
        return 0.9
    if any(word in n for word in ["gruszka", "jabl", "truskawk", "mango", "granat", "brzoskw", "morel", "porzeczk", "marakui", "pomarancz", "ananas", "wisni", "banan"]):
        return 0.8
    return 0.6


def build_weighted_ingredients(option: dict) -> list[tuple[str, float, bool]]:
    parts = [parse_ingredient(token) for token in split_ingredients(option["ingredients"])]
    specified = [(name, pct) for name, pct in parts if pct is not None]
    unspecified = [name for name, pct in parts if pct is None]

    specified_total = sum(pct for _, pct in specified)
    remaining = max(0.0, 100.0 - specified_total)
    implicit_total = sum(implicit_weight(name, option) for name in unspecified) or 1.0

    weighted = [(name, pct, False) for name, pct in specified]
    for name in unspecified:
        pct = remaining * implicit_weight(name, option) / implicit_total
        weighted.append((name, pct, True))
    return weighted


def enrich_option(option: dict, meal_name: str, context: dict) -> tuple[dict, list[dict]]:
    meal_key = normalize(meal_name)
    target_kcal = MEAL_KCAL[meal_key]
    weighted = build_weighted_ingredients(option)

    kcal_density = 0.0
    sugar_density = 0.0
    sat_density = 0.0
    missing = []
    for name, pct, estimated_pct in weighted:
        profile, matched_key = lookup_profile(name)
        if matched_key is None:
            missing.append(
                {
                    "ingredient": name,
                    "normalized": normalize(name),
                    "estimatedPercentage": round(pct, 2),
                    "percentageSource": "estimated" if estimated_pct else "api",
                    "date": context["date"],
                    "meal": context["meal"],
                    "dish": context["dish"],
                }
            )
        factor = pct / 100.0
        kcal_density += factor * profile["kcal"]
        sugar_density += factor * profile["sugars"]
        sat_density += factor * profile["sat"]

    if kcal_density <= 0:
        kcal_density = 50.0

    implied_weight_g = target_kcal * 100.0 / kcal_density
    min_portion_g, max_portion_g = PORTION_LIMITS[meal_key]
    option_name = normalize(option["name"])

    if "shake" in option_name:
        max_portion_g += 70
    if "zupa" in option_name or "krem" in option_name:
        max_portion_g += 90
    if "salatka" in option_name:
        max_portion_g += 40

    portion_g = min(max(implied_weight_g, min_portion_g), max_portion_g)

    sugars = int(round(portion_g * sugar_density / 100.0))
    sat = int(round(portion_g * sat_density / 100.0))

    enriched = dict(option)
    enriched["sugars"] = max(0, sugars)
    enriched["saturated fatty acids"] = max(0, sat)
    return enriched, missing


def print_summary(payload: dict, missing_occurrences: list[dict]) -> None:
    print(f"Saved enriched menu: {OUTPUT_PATH}")
    print(
        f"Requested range: {payload['requestedRange']['start']} -> "
        f"{payload['requestedRange']['end']}"
    )
    print(f"Available API days saved: {len(payload['byDay'])}")

    if payload["unavailableDays"]:
        print("\nDays skipped because they are not currently present in the Maczfit API:")
        for ymd in payload["unavailableDays"]:
            print(f"  - {ymd}")

    if not missing_occurrences:
        print("\nIngredient coverage: all API ingredients matched the local nutrition DB.")
        return

    print("\nMissing ingredients using fallback nutrition profiles:")
    ordered = sorted(
        missing_occurrences,
        key=lambda item: (-item["estimatedPercentage"], item["date"], item["meal"], item["dish"], item["ingredient"]),
    )
    for item in ordered:
        pct = f"{item['estimatedPercentage']:.2f}%"
        src = "API" if item["percentageSource"] == "api" else "estimated"
        print(
            f"  - {pct:>8} [{src}] {item['ingredient']} | {item['date']} | "
            f"{item['meal']} | {item['dish']}"
        )


def main() -> None:
    start, end = parse_cli_args()
    requested_days = each_ymd_inclusive(start, end)
    api_payload = fetch_api_payload()
    matched_days, missing_days = filter_requested_days(api_payload, requested_days)

    output = {
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": {
            "diet": "SMARTSTART",
            "api": DIET_MEALS_API,
        },
        "requestedRange": {"start": start, "end": end},
        "requestedDays": requested_days,
        "unavailableDays": missing_days,
        "byDay": [],
    }

    all_missing_occurrences = []
    for api_day in matched_days:
        by_meal = build_by_meal_from_api_day(api_day)
        enriched_by_meal = []
        for meal in by_meal:
            enriched_options = []
            for option in meal["options"]:
                enriched, missing = enrich_option(
                    option,
                    meal["meal"],
                    {
                        "date": api_day["date"]["value"],
                        "meal": meal["meal"],
                        "dish": option["name"],
                    },
                )
                enriched_options.append(enriched)
                all_missing_occurrences.extend(missing)
            enriched_by_meal.append({"meal": meal["meal"], "options": enriched_options})

        output["byDay"].append(
            {
                "date": api_day["date"]["value"],
                "dateLabel": api_day["date"]["human"].strip(),
                "byMeal": enriched_by_meal,
            }
        )

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print_summary(output, all_missing_occurrences)


if __name__ == "__main__":
    main()
