# Data Dictionary

## data/raw/game_awards_2014_2025.csv
One row per nominee per category, The Game Awards 2014–2025 (1,753 rows).

| Column | Meaning |
|---|---|
| year, ceremony_date | Ceremony year and date (all dates confirmed against Wikipedia) |
| category | Category name as used that year |
| category_std | Category name standardized across years (e.g. "Best Score/Soundtrack" → "Best Score and Music") |
| category_type | game, performance, adaptation, developer, esports_*, creator, student_game, fan_creation |
| nominee | Name as listed (a game, person, team, show, etc.) |
| game | The game the nomination is about (blank for esports people, events, creators) |
| credits | Developer / publisher as listed; composers or writers in some Score and Narrative years |
| status | winner, nominee, or unknown (no source confirmed a winner: 2015 Trending Gamer, 2015 Fan Creation, 2017 Chinese Fan Game Award) |
| withdrawn | True if the nomination was pulled before the ceremony |
| source | Where the row came from and any second source used to confirm winners |

## data/clean/game_key.csv
One row per unique game nominated in a game category (697 games).

| Column | Meaning |
|---|---|
| game_id | Stable slug of the title, used as the join key everywhere |
| game_title, aliases | Canonical title; other names merged into it |
| base_game_id, base_game | Parent product for expansions / editions (e.g. Shadow of the Erdtree → Elden Ring) |
| developer, publisher | Companies, semicolon-separated if more than one |
| publisher_source | credited (listed on Wikipedia), override (manually set for developer-only credits), self-published (assumed) |
| *_parent_at_first_nom, *_ticker_at_first_nom | Listed owner of the publisher / developer at the game's first nomination |
| first_year, last_year, nominations, wins | Award history summary |
| release_date | Empty for now; filled by a later script |

## data/clean/entity_ownership.csv
Who owned each company or studio, and when. Any company not listed is treated as private / independent.
`valid_from` / `valid_to` blank means "open-ended". `confidence` = medium where the closing date is approximate (month-level).

## data/clean/parent_companies.csv
Listed parent → home-exchange ticker, exchange, currency, and listing window (`listed_from` / `listed_to`).
Prices are in local currency; convert to USD (or use returns) before comparing across exchanges.

## data/clean/publisher_periods.csv
Games whose publisher changed over time (Destiny 2, No Man's Sky). These override the publisher in game_key by date.

## data/clean/nominations_enriched.csv
**The main analysis table.** One row per game-category nomination (1,370 rows), with the listed parent company and ticker of the publisher and developer *as of ceremony night*.
A blank ticker means the owner was private (or not yet / no longer listed) on that date.

## Known limitations
- Ownership dates marked `medium` confidence are accurate to roughly the month.
- Nintendo affiliates (The Pokémon Company, Game Freak, HAL, Intelligent Systems) are treated as private; games they made are linked to Nintendo when Nintendo published them.
- Minority stakes (e.g. Tencent in Epic, Larian, Ubisoft) are ignored; only controlling owners count.
- Embracer (renaming to Fellowship Entertainment), Pullup (formerly Focus) and Everplay (formerly Team17) tickers should be checked when downloading prices.
- EA was taken private in August 2026; its price history ends there.

## data/raw/prices/
Daily prices from Yahoo Finance via `python -m src.fetch_prices`, with fallbacks logged in `download_log.csv` (`source_used`):
- **ATVI** (Activision Blizzard) and **TWX** (Time Warner) are delisted; their history comes from **Tiingo** (needs a free `TIINGO_API_KEY` in `.env`). Tiingo's `adj_close` adjusts for splits and dividends, same as Yahoo.
- **Warsaw benchmark:** if the WIG20 index isn't available, the script uses **EPOL** (iShares MSCI Poland ETF, priced in USD). `exchange_benchmarks.csv` records which one was used.
- **Known gaps (excluded from the stock analysis):** **CDM.L** (Codemasters, delisted 2021, 4 nominations) and **THUNDR.ST** (Thunderful, delisted 2026, 2 nominations). No free source keeps their history; 6 of 935 listed-company nominations (<1%).
