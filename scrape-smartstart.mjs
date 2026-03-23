/**
 * Scrape Smart Start (SMARTSTART) menu for the day shown on maczfit.pl.
 * Run: node scrape-smartstart.mjs
 * Output: menu-output.json + console
 */
import { chromium } from "playwright";
import fs from "fs";

const URL =
  process.argv[2] ||
  "https://www.maczfit.pl/szczegoly-oferty/?diet=SMARTSTART&active=1&wm=true&back=true";

const OUT = "/Users/piotr.latusek/Maczfit/menu-output.json";

async function acceptCookies(page) {
  const allowAll = page
    .locator("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
    .first();
  if (await allowAll.isVisible({ timeout: 2500 }).catch(() => false)) {
    await allowAll.click();
    await page.waitForTimeout(600);
  }
}

async function readDishes(page) {
  return page.evaluate(() =>
    [
      ...document.querySelectorAll(
        ".meals-container__meal.tier-16 .meal__variant-description",
      ),
    ].map((e) => e.textContent.trim()),
  );
}

async function main() {
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

  const dateLabel = await page
    .locator(".diet-menu-choice__calendar-day-main")
    .first()
    .innerText()
    .catch(() => "");

  const meals = [
    "Śniadanie",
    "II śniadanie",
    "Obiad",
    "Podwieczorek",
    "Kolacja",
  ];

  const typeSwiper = page.locator(".swiper-type-meal_16");
  const byMeal = [];

  for (const m of meals) {
    await typeSwiper.locator(".swiper__text", { hasText: new RegExp(`^${m}$`) }).first().click();
    await page.waitForTimeout(700);
    const dishes = await readDishes(page);
    byMeal.push({ meal: m, options: dishes });
  }

  const payload = {
    scrapedAt: new Date().toISOString(),
    url: URL,
    dateLabel: dateLabel.trim().replace(/\s+/g, " "),
    byMeal,
  };

  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), "utf8");

  for (const { meal, options } of byMeal) {
    console.log(`\n${meal}`);
    for (const o of options) console.log(`  • ${o}`);
  }
  console.log(`\nSaved: ${OUT}`);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
