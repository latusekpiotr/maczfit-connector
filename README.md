# Maczfit menu scraper

This folder holds a small **Playwright** script that loads the Maczfit **Smart Start** (SMARTSTART) offer page, steps through the five daily meals in the browser, and reads the two dish names per meal from the live DOM.

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

The script moves the on-page calendar (**prev / next** boxes next to the date label) until each target day is selected, then runs the same five-meal scrape as for a single day.

## Output

- **Console** — per day: heading with ISO date and Polish label, then five meals with two dish lines each.
- **`menu-output.json`** (repo root) — machine-readable payload:
  - `scrapedAt` — ISO timestamp
  - `url` — page loaded
  - `range` — `null` for a single-day run, or `{ start, end }` when a range was requested
  - `byDay` — array of `{ date, dateLabel, byMeal }`
    - `date` — `YYYY-MM-DD` when known (range runs; single-day run parses from the label when possible)
    - `dateLabel` — text from the page (e.g. Polish weekday + date)
    - `byMeal` — `{ meal, options[] }` for Śniadanie → Kolacja

## How it works (briefly)

1. Opens the offer URL and accepts the Cookiebot “allow all” banner when present.
2. Waits for **`.swiper-type-meal_16`** (Smart Start tier in the current markup).
3. For a **date range**, uses **`.diet-menu-choice__calendar-box`** (prev/next) until the calendar shows each target day (parses **`.diet-menu-choice__calendar-day-main`**).
4. Clicks each meal label (**Śniadanie**, **II śniadanie**, **Obiad**, **Podwieczorek**, **Kolacja**).
5. After each click, collects text from **`.meals-container__meal.tier-16 .meal__variant-description`** (two nodes = two options).

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
- **Date range** — only days the site exposes in the calendar can be scraped; prev/next may be disabled at the edges, which stops the run with an error.
- **Fragile to UI changes** — relies on current Vue/DOM structure.
- **Polish locale** — page content and date labels are Polish.

## License

Personal utility; not affiliated with Maczfit. Use in line with Maczfit’s terms of service.
