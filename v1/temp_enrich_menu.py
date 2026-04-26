import json
import re
import unicodedata
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_PATH = SCRIPT_DIR / "menu-output.json"
OUTPUT_PATH = SCRIPT_DIR / "menu-output-enriched.json"

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
    ("woda", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("sol", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("witamina c", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("kawa rozpuszczalna", {"kcal": 350, "sugars": 2.0, "sat": 0.2}),
    ("przyprawa do piernika", {"kcal": 250, "sugars": 5.0, "sat": 0.5}),
    ("papryka slodka mielona", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("papryka czerwona mielona ostra", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("papryka mielona gochugaru", {"kcal": 280, "sugars": 10.0, "sat": 0.5}),
    ("pieprz czarny", {"kcal": 250, "sugars": 0.6, "sat": 1.4}),
    ("oregano", {"kcal": 260, "sugars": 4.0, "sat": 2.0}),
    ("tymianek", {"kcal": 275, "sugars": 1.7, "sat": 2.7}),
    ("majeranek", {"kcal": 270, "sugars": 4.1, "sat": 2.4}),
    ("kolendra", {"kcal": 23, "sugars": 0.9, "sat": 0.0}),
    ("bazylia", {"kcal": 23, "sugars": 0.3, "sat": 0.0}),
    ("koperek", {"kcal": 43, "sugars": 0.0, "sat": 0.1}),
    ("natka pietruszki", {"kcal": 36, "sugars": 0.9, "sat": 0.1}),
    ("szczypior", {"kcal": 30, "sugars": 1.9, "sat": 0.1}),
    ("czosnek", {"kcal": 149, "sugars": 1.0, "sat": 0.1}),
    ("cebula suszona", {"kcal": 349, "sugars": 38.0, "sat": 0.1}),
    ("cebula duszona", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("cebula czerwona", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("cebula", {"kcal": 40, "sugars": 4.2, "sat": 0.0}),
    ("mieszanka warzyw suszonych", {"kcal": 240, "sugars": 20.0, "sat": 0.3}),
    ("skrobia ziemniaczana", {"kcal": 333, "sugars": 0.0, "sat": 0.0}),
    ("zelatyna", {"kcal": 335, "sugars": 0.0, "sat": 0.0}),
    ("proszek do pieczenia", {"kcal": 53, "sugars": 0.0, "sat": 0.0}),
    ("soda oczyszczona", {"kcal": 0, "sugars": 0.0, "sat": 0.0}),
    ("mleko bez laktozy 1 5 tl", {"kcal": 46, "sugars": 5.0, "sat": 1.0}),
    ("mleko 0 5 tl", {"kcal": 37, "sugars": 5.1, "sat": 0.3}),
    ("smietanka 12", {"kcal": 136, "sugars": 4.0, "sat": 7.7}),
    ("smietanka 30", {"kcal": 292, "sugars": 3.1, "sat": 19.0}),
    ("smietana bez laktozy 18", {"kcal": 193, "sugars": 3.6, "sat": 11.3}),
    ("jogurt naturalny typu greckiego", {"kcal": 97, "sugars": 3.6, "sat": 4.8}),
    ("jogurt naturalny wysokobialkowy bez laktozy", {"kcal": 60, "sugars": 4.0, "sat": 0.3}),
    ("jogurt naturalny wysokobialkowy", {"kcal": 60, "sugars": 4.0, "sat": 0.3}),
    ("jogurt naturalny", {"kcal": 60, "sugars": 4.7, "sat": 1.0}),
    ("ricotta", {"kcal": 174, "sugars": 3.0, "sat": 10.9}),
    ("twarog sernikowy", {"kcal": 220, "sugars": 3.5, "sat": 9.0}),
    ("ser twarogowy chudy", {"kcal": 99, "sugars": 3.4, "sat": 0.5}),
    ("serek homogenizowany waniliowy", {"kcal": 160, "sugars": 13.0, "sat": 3.0}),
    ("serek smietankowy naturalny", {"kcal": 250, "sugars": 4.0, "sat": 14.0}),
    ("serek naturalny light", {"kcal": 90, "sugars": 4.0, "sat": 2.5}),
    ("ser feta bez laktozy", {"kcal": 260, "sugars": 1.5, "sat": 14.0}),
    ("ser typu feta", {"kcal": 260, "sugars": 1.5, "sat": 14.0}),
    ("ser zolty bez laktozy", {"kcal": 350, "sugars": 1.0, "sat": 19.0}),
    ("ser zolty", {"kcal": 350, "sugars": 1.0, "sat": 19.0}),
    ("ser dojrzewajacy", {"kcal": 380, "sugars": 0.5, "sat": 21.0}),
    ("ser weganski", {"kcal": 280, "sugars": 0.5, "sat": 20.0}),
    ("mozzarella mini", {"kcal": 250, "sugars": 1.0, "sat": 11.0}),
    ("jaja", {"kcal": 143, "sugars": 0.7, "sat": 3.3}),
    ("zoltko jaja", {"kcal": 322, "sugars": 0.6, "sat": 9.6}),
    ("maslo", {"kcal": 717, "sugars": 0.1, "sat": 51.0}),
    ("majonez light", {"kcal": 270, "sugars": 2.0, "sat": 2.0}),
    ("czekolada gorzka", {"kcal": 546, "sugars": 24.0, "sat": 19.0}),
    ("rodzynki", {"kcal": 299, "sugars": 59.0, "sat": 0.1}),
    ("gruszka", {"kcal": 57, "sugars": 9.8, "sat": 0.0}),
    ("jablka", {"kcal": 52, "sugars": 10.4, "sat": 0.0}),
    ("jablko", {"kcal": 52, "sugars": 10.4, "sat": 0.0}),
    ("truskawki", {"kcal": 32, "sugars": 4.9, "sat": 0.0}),
    ("mango", {"kcal": 60, "sugars": 13.7, "sat": 0.1}),
    ("granat", {"kcal": 83, "sugars": 13.7, "sat": 0.1}),
    ("brzoskwinia", {"kcal": 39, "sugars": 8.4, "sat": 0.0}),
    ("morele", {"kcal": 48, "sugars": 9.2, "sat": 0.0}),
    ("porzeczka czerwona", {"kcal": 56, "sugars": 7.4, "sat": 0.0}),
    ("pulpa z marakui", {"kcal": 97, "sugars": 11.2, "sat": 0.7}),
    ("pomarancza", {"kcal": 47, "sugars": 9.4, "sat": 0.0}),
    ("ananas", {"kcal": 50, "sugars": 9.9, "sat": 0.0}),
    ("puree wisniowe", {"kcal": 50, "sugars": 10.0, "sat": 0.1}),
    ("mus mango", {"kcal": 65, "sugars": 14.0, "sat": 0.1}),
    ("marchew", {"kcal": 41, "sugars": 4.7, "sat": 0.0}),
    ("burak", {"kcal": 43, "sugars": 6.8, "sat": 0.0}),
    ("batat", {"kcal": 86, "sugars": 4.2, "sat": 0.0}),
    ("ziemniaki", {"kcal": 77, "sugars": 0.8, "sat": 0.0}),
    ("dynia", {"kcal": 26, "sugars": 2.8, "sat": 0.1}),
    ("ogorek kiszony", {"kcal": 11, "sugars": 1.1, "sat": 0.0}),
    ("ogorek", {"kcal": 15, "sugars": 1.7, "sat": 0.0}),
    ("pomidory krojone", {"kcal": 21, "sugars": 3.9, "sat": 0.0}),
    ("pomidor czerwony", {"kcal": 18, "sugars": 2.6, "sat": 0.0}),
    ("koncentrat pomidorowy", {"kcal": 82, "sugars": 12.0, "sat": 0.0}),
    ("papryka czerwona", {"kcal": 31, "sugars": 4.2, "sat": 0.0}),
    ("cukinia", {"kcal": 17, "sugars": 2.5, "sat": 0.1}),
    ("kalafior", {"kcal": 25, "sugars": 1.9, "sat": 0.1}),
    ("szpinak", {"kcal": 23, "sugars": 0.4, "sat": 0.1}),
    ("rukola", {"kcal": 25, "sugars": 2.1, "sat": 0.1}),
    ("mix salat", {"kcal": 17, "sugars": 2.0, "sat": 0.0}),
    ("pieczarka", {"kcal": 22, "sugars": 2.0, "sat": 0.0}),
    ("kapusta kiszona", {"kcal": 19, "sugars": 1.8, "sat": 0.0}),
    ("kapusta biala", {"kcal": 25, "sugars": 3.2, "sat": 0.0}),
    ("fasolka szparagowa zielona", {"kcal": 31, "sugars": 3.3, "sat": 0.1}),
    ("kielki fasoli mung", {"kcal": 30, "sugars": 4.1, "sat": 0.0}),
    ("groszek zielony", {"kcal": 81, "sugars": 5.7, "sat": 0.1}),
    ("seler korzen", {"kcal": 42, "sugars": 1.6, "sat": 0.1}),
    ("pietruszka korzen", {"kcal": 55, "sugars": 4.8, "sat": 0.1}),
    ("ciecierzyca", {"kcal": 164, "sugars": 4.8, "sat": 0.3}),
    ("fasola biala", {"kcal": 140, "sugars": 0.3, "sat": 0.1}),
    ("fasola czarna", {"kcal": 132, "sugars": 0.3, "sat": 0.1}),
    ("fasola czerwona", {"kcal": 127, "sugars": 0.3, "sat": 0.1}),
    ("granulat sojowy", {"kcal": 330, "sugars": 7.0, "sat": 0.7}),
    ("tofu wedzone", {"kcal": 170, "sugars": 1.6, "sat": 1.3}),
    ("pasta z orzechow nerkowca", {"kcal": 587, "sugars": 5.9, "sat": 10.5}),
    ("orzeszki ziemne prazone", {"kcal": 585, "sugars": 4.7, "sat": 6.8}),
    ("orzechy nerkowca", {"kcal": 553, "sugars": 5.9, "sat": 7.8}),
    ("orzechy laskowe", {"kcal": 628, "sugars": 4.3, "sat": 4.5}),
    ("migdaly", {"kcal": 579, "sugars": 4.4, "sat": 3.8}),
    ("slonecznik", {"kcal": 584, "sugars": 2.6, "sat": 5.2}),
    ("sezam bialy", {"kcal": 573, "sugars": 0.3, "sat": 7.0}),
    ("pestki dyni", {"kcal": 559, "sugars": 1.4, "sat": 8.7}),
    ("pasta sezamowa tahini", {"kcal": 595, "sugars": 1.6, "sat": 7.0}),
    ("wiorki kokosowe", {"kcal": 660, "sugars": 7.0, "sat": 57.0}),
    ("chipsy bananowe", {"kcal": 519, "sugars": 35.0, "sat": 29.0}),
    ("zurawina suszona slodzona", {"kcal": 325, "sugars": 65.0, "sat": 0.1}),
    ("jagody goji", {"kcal": 349, "sugars": 45.0, "sat": 0.4}),
    ("platki owsiane bezglutenowe", {"kcal": 379, "sugars": 1.0, "sat": 1.2}),
    ("platki owsiane gorskie", {"kcal": 379, "sugars": 1.0, "sat": 1.2}),
    ("platki jaglane", {"kcal": 378, "sugars": 0.4, "sat": 0.7}),
    ("kasza bulgur", {"kcal": 83, "sugars": 0.1, "sat": 0.0}),
    ("ryz basmati", {"kcal": 130, "sugars": 0.1, "sat": 0.0}),
    ("ryz jasminowy", {"kcal": 130, "sugars": 0.1, "sat": 0.0}),
    ("makaron spaghetti pszenny", {"kcal": 158, "sugars": 0.6, "sat": 0.2}),
    ("makaron pszenny", {"kcal": 158, "sugars": 0.6, "sat": 0.2}),
    ("maka pszenna pelnoziarnista", {"kcal": 340, "sugars": 0.4, "sat": 0.2}),
    ("maka pszenna", {"kcal": 364, "sugars": 0.3, "sat": 0.2}),
    ("maka bezglutenowa mix", {"kcal": 360, "sugars": 2.0, "sat": 0.3}),
    ("pancakes mini", {"kcal": 227, "sugars": 11.0, "sat": 2.0}),
    ("platki zytnie", {"kcal": 335, "sugars": 1.2, "sat": 0.3}),
    ("mini pumpernikiel", {"kcal": 250, "sugars": 6.0, "sat": 0.2}),
    ("bulka dyniowa", {"kcal": 270, "sugars": 4.0, "sat": 0.5}),
    ("bulka rustykalna", {"kcal": 270, "sugars": 2.8, "sat": 0.6}),
    ("chleb zytni dyniowy", {"kcal": 240, "sugars": 5.0, "sat": 0.3}),
    ("chleb zytni ze slonecznikiem", {"kcal": 250, "sugars": 4.0, "sat": 0.4}),
    ("chleb zytni razowy", {"kcal": 230, "sugars": 3.8, "sat": 0.3}),
    ("chleb zytni", {"kcal": 230, "sugars": 3.8, "sat": 0.3}),
    ("ciabatta pszenna z suszonymi pomidorami", {"kcal": 270, "sugars": 2.5, "sat": 0.7}),
    ("ciasto na pizze", {"kcal": 270, "sugars": 3.0, "sat": 1.0}),
    ("tortilla orkiszowo owsiana", {"kcal": 290, "sugars": 2.5, "sat": 1.5}),
    ("nachosy kukurydziane", {"kcal": 490, "sugars": 1.0, "sat": 1.1}),
    ("herbatniki waniliowe bez cukru", {"kcal": 430, "sugars": 3.0, "sat": 4.0}),
    ("herbatniki kakowe bez cukru", {"kcal": 430, "sugars": 4.0, "sat": 4.0}),
    ("paluchy bezglutenowe z suszonymi pomidorami", {"kcal": 410, "sugars": 5.0, "sat": 1.0}),
    ("pierogi ruskie z tofu", {"kcal": 170, "sugars": 2.0, "sat": 1.0}),
    ("pierozki gyoza z warzywami", {"kcal": 190, "sugars": 4.0, "sat": 0.8}),
    ("tortellini ze szpinakiem i ricotta", {"kcal": 190, "sugars": 2.0, "sat": 2.2}),
    ("makaron chow mein", {"kcal": 170, "sugars": 1.0, "sat": 0.3}),
    ("makaron z manioku", {"kcal": 160, "sugars": 1.0, "sat": 0.1}),
    ("kasza manna", {"kcal": 360, "sugars": 0.4, "sat": 0.2}),
    ("kasza kuskus", {"kcal": 112, "sugars": 0.1, "sat": 0.0}),
    ("budyn w proszku o smaku waniliowym", {"kcal": 350, "sugars": 80.0, "sat": 0.2}),
    ("budyn w proszku o smaku czekoladowym", {"kcal": 360, "sugars": 75.0, "sat": 1.5}),
    ("galaretka truskawkowa", {"kcal": 330, "sugars": 80.0, "sat": 0.0}),
    ("cukier puder", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("cukier wanilinowy", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("cukier", {"kcal": 400, "sugars": 100.0, "sat": 0.0}),
    ("ksylitol", {"kcal": 240, "sugars": 0.0, "sat": 0.0}),
    ("miod pszczeli", {"kcal": 304, "sugars": 82.0, "sat": 0.0}),
    ("sos sojowy jasny", {"kcal": 53, "sugars": 4.9, "sat": 0.1}),
    ("sos sojowy bezglutenowy", {"kcal": 53, "sugars": 4.9, "sat": 0.1}),
    ("sos sriracha", {"kcal": 100, "sugars": 20.0, "sat": 0.0}),
    ("sos pikantno slodki", {"kcal": 180, "sugars": 35.0, "sat": 0.0}),
    ("sos pomidorowy z ziolami", {"kcal": 45, "sugars": 6.0, "sat": 0.0}),
    ("pasta harrisa", {"kcal": 120, "sugars": 6.0, "sat": 0.6}),
    ("pasta miso jasna", {"kcal": 199, "sugars": 6.2, "sat": 1.0}),
    ("pesto czerwone", {"kcal": 460, "sugars": 6.0, "sat": 3.5}),
    ("pesto zielone", {"kcal": 450, "sugars": 4.0, "sat": 4.0}),
    ("olej sezamowy", {"kcal": 884, "sugars": 0.0, "sat": 14.0}),
    ("oliwa z oliwek", {"kcal": 884, "sugars": 0.0, "sat": 14.0}),
    ("olej rzepakowy", {"kcal": 884, "sugars": 0.0, "sat": 7.0}),
    ("oliwki czarne", {"kcal": 115, "sugars": 0.0, "sat": 2.3}),
    ("oliwki zielone", {"kcal": 145, "sugars": 0.5, "sat": 2.0}),
    ("kapary w zalewie", {"kcal": 23, "sugars": 0.4, "sat": 0.2}),
    ("filet z piersi kurczaka", {"kcal": 165, "sugars": 0.0, "sat": 1.0}),
    ("filet z piersi indyka", {"kcal": 114, "sugars": 0.0, "sat": 0.4}),
    ("mieso drobne z indyka", {"kcal": 150, "sugars": 0.0, "sat": 2.0}),
    ("mieso mielone z kurczaka", {"kcal": 170, "sugars": 0.0, "sat": 3.0}),
    ("kielbasa krakowska", {"kcal": 300, "sugars": 1.0, "sat": 11.0}),
    ("kielbasa z kurczaka", {"kcal": 220, "sugars": 1.0, "sat": 6.0}),
    ("filet z dorsza czarnego", {"kcal": 180, "sugars": 0.0, "sat": 1.4}),
    ("bulka tarta", {"kcal": 395, "sugars": 5.0, "sat": 0.7}),
    ("rzodkiewka", {"kcal": 16, "sugars": 1.9, "sat": 0.0}),
    ("banan", {"kcal": 89, "sugars": 12.2, "sat": 0.1}),
    ("sliwki", {"kcal": 46, "sugars": 10.0, "sat": 0.0}),
    ("winogrono ciemne", {"kcal": 69, "sugars": 15.5, "sat": 0.1}),
    ("zurawina", {"kcal": 46, "sugars": 4.3, "sat": 0.1}),
    ("kukurydza", {"kcal": 96, "sugars": 6.3, "sat": 0.2}),
    ("kukurydza konserwowa", {"kcal": 96, "sugars": 4.5, "sat": 0.2}),
    ("soczewica zielona", {"kcal": 116, "sugars": 1.8, "sat": 0.1}),
    ("soczewica czerwona", {"kcal": 116, "sugars": 1.8, "sat": 0.1}),
    ("papryka", {"kcal": 31, "sugars": 4.2, "sat": 0.0}),
    ("baklazan", {"kcal": 25, "sugars": 3.5, "sat": 0.0}),
    ("por", {"kcal": 61, "sugars": 3.9, "sat": 0.0}),
    ("pomidor daktylowy czerwony", {"kcal": 18, "sugars": 2.6, "sat": 0.0}),
    ("korzen pietruszki", {"kcal": 55, "sugars": 4.8, "sat": 0.1}),
    ("pomidory suszone w oleju", {"kcal": 213, "sugars": 12.4, "sat": 1.5}),
    ("sok z limonki", {"kcal": 25, "sugars": 1.7, "sat": 0.0}),
    ("sok z cytryny", {"kcal": 22, "sugars": 2.5, "sat": 0.0}),
    ("imbir", {"kcal": 80, "sugars": 1.7, "sat": 0.2}),
    ("imbir mielony", {"kcal": 335, "sugars": 3.4, "sat": 2.6}),
    ("kurkuma", {"kcal": 312, "sugars": 3.2, "sat": 3.1}),
    ("kminek", {"kcal": 333, "sugars": 7.0, "sat": 0.6}),
    ("cynamon", {"kcal": 247, "sugars": 2.2, "sat": 0.3}),
    ("galka muszkatolowa", {"kcal": 525, "sugars": 3.0, "sat": 25.9}),
    ("kardamon", {"kcal": 311, "sugars": 0.0, "sat": 0.7}),
    ("garam masala", {"kcal": 300, "sugars": 2.0, "sat": 0.8}),
    ("ziola prowansalskie", {"kcal": 260, "sugars": 4.0, "sat": 2.0}),
    ("ziele angielskie", {"kcal": 263, "sugars": 0.0, "sat": 6.0}),
    ("lisc laurowy", {"kcal": 313, "sugars": 0.0, "sat": 2.3}),
    ("lubczyk", {"kcal": 20, "sugars": 3.0, "sat": 0.1}),
    ("posypka bruschetta", {"kcal": 300, "sugars": 12.0, "sat": 1.0}),
    ("platki suszonej papryki", {"kcal": 282, "sugars": 10.0, "sat": 0.5}),
    ("ocet balsamiczny", {"kcal": 88, "sugars": 15.0, "sat": 0.0}),
    ("ocet ryzowy", {"kcal": 20, "sugars": 0.1, "sat": 0.0}),
    ("ocet winny bialy", {"kcal": 19, "sugars": 0.1, "sat": 0.0}),
    ("musztarda sarepska", {"kcal": 140, "sugars": 6.0, "sat": 0.3}),
    ("musztarda", {"kcal": 140, "sugars": 6.0, "sat": 0.3}),
    ("ketchup", {"kcal": 112, "sugars": 22.0, "sat": 0.0}),
    ("ser kozi", {"kcal": 320, "sugars": 0.5, "sat": 21.0}),
    ("ser plesniowy typu blue", {"kcal": 353, "sugars": 0.5, "sat": 18.7}),
    ("serek naturalny bez laktozy", {"kcal": 90, "sugars": 4.0, "sat": 2.5}),
    ("serek wiejski", {"kcal": 98, "sugars": 2.7, "sat": 1.8}),
    ("serek homogenizowany naturalny", {"kcal": 110, "sugars": 4.5, "sat": 3.0}),
    ("mozzarella", {"kcal": 254, "sugars": 1.0, "sat": 13.0}),
    ("mozzarella light", {"kcal": 170, "sugars": 1.0, "sat": 8.0}),
    ("sezam czarny", {"kcal": 573, "sugars": 0.3, "sat": 7.0}),
    ("orzeszki arachidowe", {"kcal": 585, "sugars": 4.7, "sat": 6.8}),
    ("orzechy arachidowe prazone w karmelu", {"kcal": 550, "sugars": 24.0, "sat": 8.0}),
    ("orzechy wloskie", {"kcal": 654, "sugars": 2.6, "sat": 6.1}),
    ("smietana 12", {"kcal": 133, "sugars": 4.1, "sat": 7.6}),
    ("mleko 0 5 tl", {"kcal": 37, "sugars": 5.1, "sat": 0.3}),
    ("czekolada biala", {"kcal": 539, "sugars": 59.0, "sat": 20.0}),
    ("kakao o obnizonej zawartosci tluszczu", {"kcal": 230, "sugars": 1.8, "sat": 8.0}),
    ("kotleciki warzywne z grzybami", {"kcal": 170, "sugars": 3.0, "sat": 0.8}),
    ("marynowana rzodkiew zolta", {"kcal": 25, "sugars": 4.0, "sat": 0.0}),
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


def profile_for(name: str) -> dict[str, float]:
    normalized = normalize(name)
    best_match = None
    best_length = -1
    for key, values in NUTRITION_DB:
        if key in normalized and len(key) > best_length:
            best_match = values
            best_length = len(key)
    if best_match is not None:
        return best_match
    return fallback_profile(name)


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


def enrich_option(option: dict, meal_name: str) -> dict:
    meal_key = normalize(meal_name)
    target_kcal = MEAL_KCAL[meal_key]
    parts = [parse_ingredient(token) for token in split_ingredients(option["ingredients"])]
    specified = [(name, pct) for name, pct in parts if pct is not None]
    unspecified = [name for name, pct in parts if pct is None]

    specified_total = sum(pct for _, pct in specified)
    remaining = max(0.0, 100.0 - specified_total)
    implicit_total = sum(implicit_weight(name, option) for name in unspecified) or 1.0

    weighted = []
    for name, pct in specified:
        weighted.append((name, pct))
    for name in unspecified:
        pct = remaining * implicit_weight(name, option) / implicit_total
        weighted.append((name, pct))

    kcal_density = 0.0
    sugar_density = 0.0
    sat_density = 0.0
    for name, pct in weighted:
        profile = profile_for(name)
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
    return enriched


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    output = json.loads(json.dumps(data, ensure_ascii=False))
    for day in output["byDay"]:
        for meal in day["byMeal"]:
            meal["options"] = [enrich_option(option, meal["meal"]) for option in meal["options"]]

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
