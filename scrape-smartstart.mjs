/**
 * Scrape Smart Start (SMARTSTART) menu from maczfit.pl.
 *
 * Usage:
 *   node scrape-smartstart.mjs
 *   node scrape-smartstart.mjs <URL>
 *   node scrape-smartstart.mjs <YYYY-MM-DD> <YYYY-MM-DD>
 *   node scrape-smartstart.mjs <YYYY-MM-DD> <YYYY-MM-DD> <URL>
 *
 * Output: menu-output.json (repo root) + console
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_URL =
  "https://www.maczfit.pl/szczegoly-oferty/?diet=SMARTSTART&active=1&wm=true&back=true";
const OUT = path.join(__dirname, "menu-output.json");

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const MEALS = [
  "Śniadanie",
  "II śniadanie",
  "Obiad",
  "Podwieczorek",
  "Kolacja",
];

/** Same tier as `.swiper-type-meal_16` / Smart Start — public menu JSON includes `ingredients` per dish. */
const DIET_MEALS_API = "https://www.maczfit.pl/api/v2/meals/diet/16";

let cachedDietMealsJson = null;

async function loadDietMealsJson() {
  if (cachedDietMealsJson) return cachedDietMealsJson;
  const res = await fetch(DIET_MEALS_API);
  if (!res.ok) {
    throw new Error(`GET ${DIET_MEALS_API} failed: ${res.status}`);
  }
  cachedDietMealsJson = await res.json();
  return cachedDietMealsJson;
}

function normalizeIngredients(s) {
  if (s == null || s === "") return "";
  return String(s).replace(/\s+/g, " ").trim();
}

function buildByMealFromApiDay(apiDay) {
  const byMeal = [];
  for (const label of MEALS) {
    const rows = apiDay.meals.filter((x) => x.type.human === label);
    if (rows.length !== 2) {
      throw new Error(
        `API: expected 2 options for "${label}" on ${apiDay.date.value}, got ${rows.length}`,
      );
    }
    byMeal.push({
      meal: label,
      options: rows.map((x) => ({
        name: x.name.trim(),
        ingredients: normalizeIngredients(x.ingredients),
      })),
    });
  }
  return byMeal;
}

async function findApiDayForYmd(ymd) {
  if (!ymd) return null;
  try {
    const json = await loadDietMealsJson();
    return json.data?.find((d) => d.date.value === ymd) ?? null;
  } catch (e) {
    console.warn("Meals API unavailable, falling back to DOM names only:", e.message);
    return null;
  }
}

function parseArgs() {
  const raw = process.argv.slice(2);
  if (raw.length === 0) {
    return { url: DEFAULT_URL, range: null };
  }
  if (raw.length >= 2 && ISO_DATE.test(raw[0]) && ISO_DATE.test(raw[1])) {
    const url = raw.find((a) => a.startsWith("http")) || DEFAULT_URL;
    return { url, range: { start: raw[0], end: raw[1] } };
  }
  if (raw.length === 1 && raw[0].startsWith("http")) {
    return { url: raw[0], range: null };
  }
  console.error(`Usage:
  node scrape-smartstart.mjs
  node scrape-smartstart.mjs <URL>
  node scrape-smartstart.mjs <YYYY-MM-DD> <YYYY-MM-DD>
  node scrape-smartstart.mjs <YYYY-MM-DD> <YYYY-MM-DD> <URL>`);
  process.exit(1);
}

function parseISODateOnly(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function ymdFromDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function eachYmdInclusive(startStr, endStr) {
  const start = parseISODateOnly(startStr);
  const end = parseISODateOnly(endStr);
  if (end < start) {
    throw new Error(`end date ${endStr} is before start date ${startStr}`);
  }
  const out = [];
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    out.push(ymdFromDate(d));
  }
  return out;
}

function parsePlDateFromLabel(text) {
  const m = text.replace(/\s+/g, " ").match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/);
  if (!m) return null;
  return new Date(+m[3], +m[2] - 1, +m[1]);
}

function cmpYmd(a, b) {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

async function acceptCookies(page) {
  for (let i = 0; i < 4; i++) {
    const allowAll = page
      .locator("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
      .first();
    if (await allowAll.isVisible({ timeout: 2000 }).catch(() => false)) {
      await allowAll.click({ force: true });
      await page.waitForTimeout(400);
    }
    const dlg = page.locator("#CybotCookiebotDialog");
    if (!(await dlg.isVisible().catch(() => false))) break;
  }
  await page.locator("#CybotCookiebotDialog").waitFor({ state: "hidden", timeout: 15000 }).catch(() => {});
}

async function readDishNames(page) {
  return page.evaluate(() =>
    [
      ...document.querySelectorAll(
        ".meals-container__meal.tier-16 .meal__variant-description",
      ),
    ].map((e) => e.textContent.trim()),
  );
}

async function getCurrentYmd(page) {
  const label = await page
    .locator(".diet-menu-choice__calendar-day-main")
    .first()
    .innerText();
  const d = parsePlDateFromLabel(label);
  if (!d) {
    throw new Error(`Could not parse date from calendar label: ${JSON.stringify(label)}`);
  }
  return ymdFromDate(d);
}

function calendarNavBoxes(page) {
  const boxes = page.locator(".diet-menu-choice__calendar-boxes .diet-menu-choice__calendar-box");
  return { prev: boxes.nth(0), next: boxes.nth(1) };
}

async function waitUntilYmdChanges(page, previousYmd, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await page.waitForTimeout(200);
    const now = await getCurrentYmd(page);
    if (now !== previousYmd) return;
  }
  throw new Error(`Calendar stayed on ${previousYmd} for ${timeoutMs}ms`);
}

async function clickCalendarToward(page, targetYmd) {
  const cur = await getCurrentYmd(page);
  if (cur === targetYmd) return;
  const { prev, next } = calendarNavBoxes(page);
  const box = cmpYmd(cur, targetYmd) > 0 ? prev : next;
  const disabled = await box.evaluate((el) => el.classList.contains("disabled-date"));
  if (disabled) {
    throw new Error(
      `Cannot reach ${targetYmd} from ${cur}: calendar navigation is disabled (boundary or unavailable day).`,
    );
  }
  await box.click();
  await waitUntilYmdChanges(page, cur);
}

async function navigateToYmd(page, targetYmd) {
  const maxSteps = 400;
  for (let i = 0; i < maxSteps; i++) {
    const cur = await getCurrentYmd(page);
    if (cur === targetYmd) return;
    await clickCalendarToward(page, targetYmd);
  }
  throw new Error(`Could not navigate to ${targetYmd} within ${maxSteps} steps`);
}

async function scrapeMealsForDay(page, ymd) {
  const domDateLabel = await page
    .locator(".diet-menu-choice__calendar-day-main")
    .first()
    .innerText()
    .catch(() => "");

  const apiDay = await findApiDayForYmd(ymd);

  if (apiDay) {
    try {
      return {
        dateLabel: apiDay.date.human.trim().replace(/\s+/g, " "),
        byMeal: buildByMealFromApiDay(apiDay),
      };
    } catch (e) {
      console.warn("Using DOM for this day (API shape mismatch):", e.message);
    }
  }

  await page.waitForSelector(".swiper-type-meal_16", { timeout: 30000 });
  const typeSwiper = page.locator(".swiper-type-meal_16");
  const byMeal = [];

  for (const m of MEALS) {
    await typeSwiper.locator(".swiper__text", { hasText: new RegExp(`^${m}$`) }).first().click();
    await page.waitForTimeout(700);
    const names = await readDishNames(page);
    byMeal.push({
      meal: m,
      options: names.map((name) => ({ name, ingredients: "" })),
    });
  }

  return {
    dateLabel: domDateLabel.trim().replace(/\s+/g, " "),
    byMeal,
  };
}

async function main() {
  const { url: URL, range } = parseArgs();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    locale: "pl-PL",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 90000 });
  await acceptCookies(page);
  await page.waitForTimeout(4000);

  await page.waitForSelector(".swiper-type-meal_16", { timeout: 30000 });

  let byDay;

  if (range) {
    const days = eachYmdInclusive(range.start, range.end);
    byDay = [];
    for (const ymd of days) {
      await navigateToYmd(page, ymd);
      await page.waitForTimeout(500);
      const { dateLabel, byMeal } = await scrapeMealsForDay(page, ymd);
      byDay.push({ date: ymd, dateLabel, byMeal });
    }
  } else {
    const calLabel = await page
      .locator(".diet-menu-choice__calendar-day-main")
      .first()
      .innerText()
      .catch(() => "");
    const parsed = parsePlDateFromLabel(calLabel);
    const ymd = parsed ? ymdFromDate(parsed) : null;
    const { dateLabel, byMeal } = await scrapeMealsForDay(page, ymd);
    byDay = [{ date: ymd, dateLabel, byMeal }];
  }

  const payload = {
    scrapedAt: new Date().toISOString(),
    url: URL,
    range: range ? { start: range.start, end: range.end } : null,
    byDay,
  };

  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), "utf8");

  for (const day of byDay) {
    const head = day.date ? `\n=== ${day.date} (${day.dateLabel}) ===` : `\n=== ${day.dateLabel} ===`;
    console.log(head);
    for (const { meal, options } of day.byMeal) {
      console.log(`\n${meal}`);
      for (const o of options) {
        console.log(`  • ${o.name}`);
        if (o.ingredients) {
          const short =
            o.ingredients.length > 120 ? `${o.ingredients.slice(0, 120)}…` : o.ingredients;
          console.log(`    ${short}`);
        }
      }
    }
  }
  console.log(`\nSaved: ${OUT}`);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
