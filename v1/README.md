# Maczfit menu scraper

This folder holds a small **Playwright** script that loads the Maczfit **Smart Start** (SMARTSTART) offer page, aligns the on-page calendar to each target day, and builds **five meals × two options** with **dish names** and **ingredient lists** (same comma-separated format as in the meal-details view, e.g. `Jaja (39%), Pomidor…`).

It was kept **outside** the `qna-service` repository on purpose.

## Prerequisites

- **Node.js** (LTS recommended)
- Network access to `maczfit.pl`

## First-time setup

From the repository root (after `git clone`):

```bash
npm install
npx playwright install chromium
```

`npm install` pulls in the `playwright` package; `playwright install chromium` downloads the browser binary Playwright uses.

## Run the scraper

```bash
npm run scrape
```

Or directly:

```bash
node scrape-smartstart.mjs
```

### Custom URL

```bash
node scrape-smartstart.mjs 'https://www.maczfit.pl/szczegoly-oferty/?diet=SMARTSTART&active=1&wm=true&back=true'
```

### Date range (inclusive)

Use two **ISO dates** (`YYYY-MM-DD`) to scrape every calendar day in the range, including both endpoints:

```bash
node scrape-smartstart.mjs 2026-03-20 2026-03-27
```

Optional **URL** as a third argument (same diet parameters as you need):

```bash
node scrape-smartstart.mjs 2026-03-20 2026-03-27 'https://www.maczfit.pl/szczegoly-oferty/?diet=SMARTSTART&active=1&wm=true&back=true'
```

The script moves the on-page calendar (**prev / next** boxes next to the date label) until each target day is selected, then collects that day’s menu (names + ingredients) as described below.

## Output

- **Console** — per day: heading with ISO date and Polish label, then five meals; each option prints **name** and a **shortened** ingredient line when present.
- **`menu-output.json`** (repo root) — machine-readable payload:
  - `scrapedAt` — ISO timestamp
  - `url` — page loaded
  - `range` — `null` for a single-day run, or `{ start, end }` when a range was requested
  - `byDay` — array of `{ date, dateLabel, byMeal }`
    - `date` — `YYYY-MM-DD` when known (range runs; single-day run parses from the label when possible)
    - `dateLabel` — Polish weekday + date (from the public menu API when that day is found there, otherwise from the calendar strip on the page)
    - `byMeal` — `{ meal, options[] }` for Śniadanie → Kolacja
    - each **option** is `{ name, ingredients }` — `ingredients` is one string, comma-separated, like on the site (percentages in parentheses where the API provides them)

## How it works (briefly)

1. Opens the offer URL and accepts the Cookiebot “allow all” banner when present (with retries so clicks are not blocked by the overlay).
2. Waits for **`.swiper-type-meal_16`** (Smart Start tier in the current markup).
3. For a **date range**, uses **`.diet-menu-choice__calendar-box`** (prev/next) until the calendar shows each target day (parses **`.diet-menu-choice__calendar-day-main`**).
4. Loads **`https://www.maczfit.pl/api/v2/meals/diet/16`** (Smart Start) once per run and, when that payload contains the target **ISO date**, builds all five meals and both options **including `ingredients`** from the API (same text as behind “Szczegóły posiłku” on the site). No modal automation is required for those days.
5. If the target day is **not** in that API batch, falls back to clicking each meal tab and reading only **names** from **`.meals-container__meal.tier-16 .meal__variant-description`**; `ingredients` is then an empty string.

If Maczfit changes CSS classes or the tier id (`swiper-type-meal_16`, `tier-16`), update the selectors in `scrape-smartstart.mjs`.

## Files

| File | Purpose |
|------|---------|
| `scrape-smartstart.mjs` | Playwright scraper entrypoint |
| `menu-output.json` | Last run result (overwritten each run; gitignored) |
| `package.json` | npm metadata and dependencies |
| `README.md` | This documentation |

## Limitations

- **Smart Start only** — tuned for SMARTSTART / tier 16. Other “Wybór menu” tiers use different swiper classes (`swiper-type-meal_4`, `_11`, `_8`, etc.).
- **Ingredients** — filled from the public `meals/diet/16` JSON when your target date appears in that response (a rolling multi-day window). Calendar days **outside** that window still get **names** from the DOM but **`ingredients` will be empty** unless Maczfit extends the API or you add another data source.
- **Date range** — only days the site exposes in the calendar can be scraped; prev/next may be disabled at the edges, which stops the run with an error.
- **Fragile to UI changes** — relies on current Vue/DOM structure for the fallback path and calendar navigation.
- **Polish locale** — page content and date labels are Polish.

## License

Personal utility; not affiliated with Maczfit. Use in line with Maczfit’s terms of service.
