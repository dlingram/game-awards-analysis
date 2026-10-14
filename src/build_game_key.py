"""Build the game key, a dated ownership table, parent-company tickers, and an
enriched nominations file that joins each nomination to the listed company that
owned its publisher (and developer) on ceremony night.

Run from the project root:  python -m src.build_game_key

Outputs (in data/clean/):
  game_key.csv              one row per game (game_id, title, base game, developer, publisher)
  entity_ownership.csv      company/studio -> parent company, with valid_from / valid_to
  parent_companies.csv      parent company -> ticker, exchange, currency, listing dates
  publisher_periods.csv     the few games whose publisher changed over time
  nominations_enriched.csv  every game-category nomination with parent + ticker as of ceremony date
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

from src.config import RAW, CLEAN
OUT = CLEAN
OUT.mkdir(exist_ok=True)
awards = pd.read_csv(RAW / "game_awards_2014_2025.csv", encoding="utf-8-sig",
                     keep_default_na=False)
awards["ceremony_date"] = pd.to_datetime(awards["ceremony_date"])

# ---------------------------------------------------------------- titles
ALIASES = {  # variant title -> canonical title (same product)
    "Hearthstone: Heroes of Warcraft": "Hearthstone",
    "Life Is Strange 2: Episode 1": "Life Is Strange 2",
}
BASE_GAME = {  # expansion / edition / live-service successor -> base product
    "The Witcher 3: Wild Hunt - Blood and Wine": "The Witcher 3: Wild Hunt",
    "Destiny: The Taken King": "Destiny",
    "Destiny 2: Forsaken": "Destiny 2", "Destiny 2: Beyond Light": "Destiny 2",
    "Destiny 2: The Witch Queen": "Destiny 2", "Destiny 2: The Final Shape": "Destiny 2",
    "Final Fantasy XIV: Dawntrail": "Final Fantasy XIV",
    "Elden Ring: Shadow of the Erdtree": "Elden Ring",
    "Monster Hunter World: Iceborne": "Monster Hunter: World",
    "Cyberpunk 2077: Phantom Liberty": "Cyberpunk 2077",
    "Diablo IV: Vessel of Hatred": "Diablo IV",
    "Street Fighter V: Arcade Edition": "Street Fighter V",
    "Street Fighter V: Champion Edition": "Street Fighter V",
    "Mortal Kombat 11 Ultimate": "Mortal Kombat 11",
    "Killer Instinct: Season Two": "Killer Instinct", "Killer Instinct: Season Three": "Killer Instinct",
    "Persona 5 Royal": "Persona 5",
    "Grand Theft Auto Online": "Grand Theft Auto V",
    "XCOM 2: War of the Chosen": "XCOM 2",
    "The Last of Us: Left Behind": "The Last of Us",
    "World of Warcraft: Legion": "World of Warcraft",
    "Counter-Strike: Global Offensive": "Counter-Strike", "Counter-Strike 2": "Counter-Strike",
}

def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")

# ---------------------------------------------------------------- credits
# Rows whose credits are people (composers / writers), not companies
PEOPLE_CREDIT_ROWS = {("Best Score/Soundtrack", 2014), ("Best Score/Music", 2018),
                      ("Best Narrative", 2020)} | {("Best Score and Music", y)
                                                   for y in (2020, 2021, 2022, 2023, 2025)}
# Developer-only credits where a different company published the game
PUBLISHER_OVERRIDE = {
    "Abzû": "505 Games", "Bayonetta 2": "Nintendo", "Bloodborne": "Sony Interactive Entertainment",
    "Dark Souls II": "Bandai Namco Entertainment", "Dark Souls III": "Bandai Namco Entertainment",
    "Destiny": "Activision", "Destiny: The Taken King": "Activision",
    "Ever Oasis": "Nintendo", "Evolve": "2K", "Fantasia: Music Evolved": "Disney Interactive",
    "Farpoint": "Sony Interactive Entertainment",
    "Fire Emblem Fates": "Nintendo", "Fire Emblem Heroes": "Nintendo",
    "Fire Emblem Echoes: Shadows of Valentia": "Nintendo", "Firewatch": "Panic",
    "Forza Horizon 2": "Microsoft Studios", "Forza Horizon 3": "Microsoft Studios",
    "Halo Wars 2": "Microsoft Studios", "Hitman": "Square Enix",
    "Killer Instinct: Season Three": "Microsoft Studios",
    "Life Is Strange": "Square Enix", "Life Is Strange: Before the Storm": "Square Enix",
    "Lone Echo": "Oculus Studios", "Marvel's Spider-Man": "Sony Interactive Entertainment",
    "Metal Gear Solid V: The Phantom Pain": "Konami", "Monster Hunter Stories": "Capcom",
    "Night in the Woods": "Finji", "Nioh": "Sony Interactive Entertainment",
    "Nioh 2": "Sony Interactive Entertainment", "Ori and the Blind Forest": "Microsoft Studios",
    "Overcooked": "Team17", "Pac-Man 256": "Bandai Namco Entertainment",
    "Persona 4 Arena Ultimax": "Atlus", "Pillars of Eternity": "Paradox Interactive",
    "Pokkén Tournament": "Nintendo", "Pokémon Omega Ruby and Alpha Sapphire": "Nintendo",
    "Poochy & Yoshi's Woolly World": "Nintendo", "Project Cars 2": "Bandai Namco Entertainment",
    "Quantum Break": "Microsoft Studios", "Ratchet & Clank": "Sony Interactive Entertainment",
    "Rise of the Tomb Raider": "Square Enix", "Sonic Mania": "Sega",
    "South Park: The Stick of Truth": "Ubisoft",
    "Super Smash Bros. for Nintendo 3DS": "Nintendo", "Super Smash Bros. for Wii U": "Nintendo",
    "Sunset Overdrive": "Microsoft Studios", "The Banner Saga 2": "Versus Evil",
    "The Last Guardian": "Sony Interactive Entertainment", "Titanfall": "Electronic Arts",
    "Titanfall 2": "Electronic Arts", "Tomb Raider: Definitive Edition": "Square Enix",
    "Until Dawn": "Sony Interactive Entertainment", "Xenoblade Chronicles X": "Nintendo",
    "Downwell": "Devolver Digital", "Block'hood": "Devolver Digital",
    "My Friend Pedro": "Devolver Digital", "Slay the Spire": "Humble Bundle",
    "Mr. Shifty": "tinyBuild", "Orwell": "Surprise Attack",
    "Disney Infinity: Marvel Super Heroes": "Disney Interactive",
    "Disney Infinity 3.0": "Disney Interactive", "Monster Hunter Now": "Niantic",
}
# Games whose publisher changed over time (applied by ceremony date)
PUBLISHER_PERIODS = [
    ("Destiny 2", "Activision", "2017-01-01", "2018-12-31",
     "Activision published Destiny 2 until Bungie took over publishing in Jan 2019"),
    ("Destiny 2", "Bungie", "2019-01-01", "2099-12-31", "Self-published by Bungie from 2019"),
    ("No Man's Sky", "Sony Interactive Entertainment", "2014-01-01", "2016-12-31",
     "Sony co-published the 2016 PS4 launch"),
    ("No Man's Sky", "Hello Games", "2017-01-01", "2099-12-31", "Self-published after launch"),
]
COMMA_NAMES = {"Thekla, Inc."}

def split_entities(part):
    for n in COMMA_NAMES:
        part = part.replace(n, n.replace(",", "§"))
    out = [e.strip().replace("§", ",") for e in re.split(r",| and ", part) if e.strip()]
    return out

# ---------------------------------------------------------------- ownership
# (entity, parent company, valid_from, valid_to, confidence, note)
# Any entity not listed here is treated as independent / privately held.
O = []
def own(entities, parent, start="1900-01-01", end="2099-12-31", conf="high", note=""):
    for e in entities:
        O.append((e, parent, start, end, conf, note))

own(["Microsoft Studios", "Xbox Game Studios", "343 Industries", "The Coalition", "Turn 10 Studios",
     "Rare", "World's Edge"], "Microsoft")
own(["Mojang", "Mojang Studios"], "Microsoft", "2014-11-06")
own(["Playground Games", "Ninja Theory", "Compulsion Games"], "Microsoft", "2018-06-10",
    conf="medium", note="Acquisitions announced at E3 2018")
own(["Obsidian Entertainment", "inXile Entertainment"], "Microsoft", "2018-11-10", conf="medium")
own(["Double Fine", "Double Fine Productions"], "Microsoft", "2019-06-09", conf="medium")
own(["Bethesda Softworks", "Bethesda Game Studios", "id Software", "Arkane Studios",
     "MachineGames"], "ZeniMax Media (private)", "1900-01-01", "2021-03-08")
own(["Bethesda Softworks", "Bethesda Game Studios", "id Software", "Arkane Studios",
     "MachineGames"], "Microsoft", "2021-03-09")
own(["Tango Gameworks"], "ZeniMax Media (private)", "1900-01-01", "2021-03-08")
own(["Tango Gameworks"], "Microsoft", "2021-03-09", "2024-08-11")
own(["Tango Gameworks"], "Krafton", "2024-08-12", conf="medium")
ABK = ["Activision", "Blizzard Entertainment", "Treyarch", "Infinity Ward", "Sledgehammer Games",
       "Raven Software", "High Moon Studios", "Beenox", "Vicarious Visions", "Blizzard Team 3",
       "Blizzard Albany"]
own(ABK, "Activision Blizzard", "1900-01-01", "2023-10-12")
own(ABK, "Microsoft", "2023-10-13")
own(["Toys for Bob"], "Activision Blizzard", "1900-01-01", "2023-10-12")
own(["Toys for Bob"], "Microsoft", "2023-10-13", "2024-02-29", note="Went independent in 2024")

own(["Sony Interactive Entertainment", "Naughty Dog", "Santa Monica Studio", "Guerrilla Games",
     "Sucker Punch Productions", "Polyphony Digital", "San Diego Studio", "Japan Studio",
     "London Studio", "Media Molecule", "Pixelopus", "Team Asobi", "PlayStation Productions"],
    "Sony Group")
own(["Insomniac Games"], "Sony Group", "2019-11-15", conf="medium")
own(["Housemarque"], "Sony Group", "2021-06-29")
own(["Firesprite"], "Sony Group", "2021-09-08", conf="medium")
own(["Nixxes Software"], "Sony Group", "2021-07-01", conf="medium")
own(["Bungie"], "Sony Group", "2022-07-15")

own(["Electronic Arts", "EA Sports", "EA DICE", "EA Canada", "EA Vancouver", "EA Romania", "BioWare",
     "Motive Studio", "Motive Studios", "Battlefield Studios", "Criterion Games"], "Electronic Arts")
own(["Respawn Entertainment"], "Electronic Arts", "2017-12-01")
own(["Codemasters"], "Codemasters Group", "2018-06-01", "2021-02-17", conf="medium",
    note="Listed on AIM from its June 2018 IPO")
own(["Codemasters"], "Electronic Arts", "2021-02-18")

own(["2K", "2K Games", "2K Sports", "Visual Concepts", "Firaxis Games", "Hangar 13",
     "Rockstar Games", "Rockstar North"], "Take-Two Interactive")
own(["Private Division"], "Take-Two Interactive", "1900-01-01", "2024-11-14", conf="medium",
    note="Sold to an Annapurna-led group in Nov 2024")
own(["Gearbox Software", "Gearbox Publishing"], "Embracer Group", "2021-04-01", "2024-06-05",
    conf="medium")
own(["Gearbox Software", "Gearbox Publishing"], "Take-Two Interactive", "2024-06-06")

own(["Deep Silver", "Koch Media", "Plaion", "Dambuster Studios"], "Embracer Group", "2018-02-14")
own(["THQ Nordic", "HandyGames"], "Embracer Group", "2017-01-01", conf="medium")
own(["Warhorse Studios"], "Embracer Group", "2019-02-13", conf="medium")
own(["Milestone"], "Embracer Group", "2019-08-01", conf="medium")
own(["4A Games"], "Embracer Group", "2020-08-01", conf="medium")
own(["Vertigo Games"], "Embracer Group", "2020-01-01", conf="medium")
own(["Coffee Stain Studios"], "Embracer Group", "2018-11-01", "2025-12-31", conf="medium",
    note="Spun off as Coffee Stain Group in 2025")
own(["Tripwire Interactive"], "Embracer Group", "2021-08-01", conf="medium")
own(["Saber Interactive"], "Embracer Group", "2020-02-01", "2024-03-27", conf="medium",
    note="Sold to Beacon Interactive (private) in Mar 2024")
own(["3D Realms", "Slipgate Ironworks"], "Embracer Group", "2021-08-01", "2024-03-27",
    conf="medium", note="Left with Saber in Mar 2024")
own(["Eidos Montréal", "Eidos-Montréal", "Crystal Dynamics", "Square Enix Montréal"],
    "Square Enix Holdings", "1900-01-01", "2022-08-25")
own(["Eidos Montréal", "Eidos-Montréal", "Crystal Dynamics", "Square Enix Montréal"],
    "Embracer Group", "2022-08-26")
own(["IO Interactive"], "Square Enix Holdings", "1900-01-01", "2017-06-15",
    note="Management buyout June 2017")
own(["Square Enix"], "Square Enix Holdings")
own(["Applibot"], "CyberAgent")

own(["Sega", "Atlus", "Ryu Ga Gotoku Studio", "Sonic Team", "Creative Assembly",
     "The Creative Assembly", "Studio Zero"], "Sega Sammy Holdings")
own(["Two Point Studios"], "Sega Sammy Holdings", "2019-05-01", conf="medium")
own(["Relic Entertainment"], "Sega Sammy Holdings", "1900-01-01", "2024-03-31", conf="medium")
own(["Amplitude Studios"], "Sega Sammy Holdings", "2016-07-01", "2024-05-31", conf="medium")
own(["Rovio Entertainment"], "Sega Sammy Holdings", "2023-08-01", conf="medium")
own(["Bandai Namco", "Bandai Namco Games", "Bandai Namco Entertainment", "Bandai Namco Studios"],
    "Bandai Namco Holdings")
own(["FromSoftware", "Spike Chunsoft"], "Kadokawa", "2014-05-01", conf="medium")
own(["Konami", "Konami Digital Entertainment", "PES Productions"], "Konami Group")
own(["Kojima Productions"], "Konami Group", "1900-01-01", "2015-12-15",
    note="Became independent Dec 2015")
own(["Team Ninja", "Koei Tecmo"], "Koei Tecmo Holdings")
own(["Capcom"], "Capcom")
own(["Nintendo", "Nintendo EAD", "Nintendo EPD", "Nintendo SPD", "Nintendo Cube", "NDcube",
     "Monolith Soft", "Retro Studios"], "Nintendo")
own(["Next Level Games"], "Nintendo", "2021-01-05")
own(["Ubisoft", "Ubisoft Montreal", "Ubisoft Quebec", "Ubisoft Montpellier", "Ubisoft Toronto",
     "Ubisoft Milan", "Ubisoft Paris", "Ubisoft Shanghai", "Ubisoft Kiev", "Ubisoft Ivory Tower",
     "RedLynx", "Blue Byte", "Massive Entertainment", "Red Storm Entertainment"], "Ubisoft")
WB = ["Warner Bros. Games", "Warner Bros. Interactive Entertainment", "WB Games",
      "NetherRealm Studios", "NetherRealm", "Monolith Productions", "Rocksteady Studios",
      "Traveller's Tales", "TT Fusion", "Player First Games"]
own(WB, "Time Warner", "1900-01-01", "2018-06-14")
own(WB, "AT&T", "2018-06-15", "2022-04-07")
own(WB, "Warner Bros. Discovery", "2022-04-08")
own(["Avalanche Software"], "Walt Disney", "1900-01-01", "2016-12-31")
own(["Avalanche Software"], "Time Warner", "2017-01-01", "2018-06-14")
own(["Avalanche Software"], "AT&T", "2018-06-15", "2022-04-07")
own(["Avalanche Software"], "Warner Bros. Discovery", "2022-04-08")
own(["Disney Interactive", "Disney Electronic Content"], "Walt Disney")
own(["Riot Games", "TiMi Studios", "TiMi Studio Group", "Lightspeed & Quantum",
     "Lightspeed & Quantum Studio", "Level Infinite", "Tencent Games"], "Tencent")
own(["Radiant Entertainment"], "Tencent", "2016-03-01", conf="medium", note="Acquired by Riot")
own(["Supercell"], "Tencent", "2016-06-21")
own(["Funcom"], "Tencent", "2020-02-01", conf="medium")
own(["NetEase", "NetEase Games"], "NetEase")
own(["Quantic Dream"], "NetEase", "2022-08-31")
own(["Nexon", "Neople", "Mintrocket"], "Nexon")
own(["Embark Studios"], "Nexon", "2019-11-01", conf="medium")
own(["PUBG Corporation", "Krafton"], "Krafton")
own(["Oculus Studios"], "Meta Platforms")
own(["Beat Games"], "Meta Platforms", "2019-11-26")
own(["Sanzaru Games"], "Meta Platforms", "2020-02-25", conf="medium")
own(["Ready at Dawn"], "Meta Platforms", "2020-06-22", conf="medium")
own(["Camouflaj"], "Meta Platforms", "2022-08-01", conf="medium")
own(["Twisted Pixel Games"], "Meta Platforms", "2023-01-01", conf="medium")
own(["Owlchemy Labs"], "Alphabet", "2017-05-09", conf="medium")
own(["Amazon Games"], "Amazon")
own(["Night School Studio"], "Netflix", "2021-09-28")
own(["Cygames"], "CyberAgent")
own(["DeNA"], "DeNA")
own(["Netmarble"], "Netmarble")
own(["Kingsoft"], "Kingsoft")
own(["CD Projekt", "CD Projekt Red", "CD Projekt RED"], "CD Projekt")
own(["11 bit studios", "11 Bit Studios", "11 bit Studios"], "11 bit studios")
own(["tinyBuild"], "tinyBuild")
own(["Gunfire Games"], "Embracer Group", "2018-12-01", conf="medium")
own(["Splash Damage"], "Tencent", "2020-01-01", "2024-12-31", conf="medium")
own(["Remedy Entertainment"], "Remedy Entertainment")
own(["Paradox Interactive", "Paradox Development Studio"], "Paradox Interactive")
own(["Harebrained Schemes"], "Paradox Interactive", "2018-06-01", "2023-12-31", conf="medium")
own(["Triumph Studios"], "Paradox Interactive", "2017-06-01", conf="medium")
own(["Colossal Order"], "Paradox Interactive", "2022-06-01", conf="medium")
own(["505 Games"], "Digital Bros")
own(["Focus Home Interactive", "Focus Entertainment"], "Pullup Entertainment")
own(["Dotemu"], "Pullup Entertainment", "2021-07-01", conf="medium")
own(["Dontnod Entertainment", "Don't Nod"], "Don't Nod")
own(["Devolver Digital"], "Devolver Digital")
own(["Team17"], "Everplay Group")
own(["Thunderful Publishing"], "Thunderful Group", "1900-01-01", "2025-08-28")
own(["Thunderful Publishing"], "Atari SA", "2025-08-29", conf="medium",
    note="Atari took ~82% via a directed share issue in Aug 2025")
own(["Frontier Developments"], "Frontier Developments")
own(["Bloober Team"], "Bloober Team")
own(["Shift Up"], "Shift Up")
own(["Neowiz"], "Neowiz")
own(["Digital Eclipse", "Atari"], "Atari SA")
own(["Digital Eclipse"], "Atari SA", "2023-11-01", conf="medium")
own(["CCP Games"], "Pearl Abyss", "2018-10-01", conf="medium")
own(["Marvelous Entertainment"], "Marvelous")
own(["Black Wings Game Studio"], "Perfect World", conf="medium")

# Remove the blanket Digital Eclipse row added above (only the dated one applies)
O = [r for r in O if not (r[0] == "Digital Eclipse" and r[2] == "1900-01-01")]

# parent -> ticker (home exchange), exchange, currency, listed_from, listed_to, note
PARENTS = {
    "Microsoft": ("MSFT", "NASDAQ", "USD", "", "", ""),
    "Sony Group": ("6758.T", "Tokyo", "JPY", "", "", ""),
    "Nintendo": ("7974.T", "Tokyo", "JPY", "", "", ""),
    "Electronic Arts": ("EA", "NASDAQ", "USD", "", "2026-08-04",
                        "Taken private by PIF / Silver Lake / Affinity; closing announced 4 Aug 2026"),
    "Activision Blizzard": ("ATVI", "NASDAQ", "USD", "", "2023-10-13", "Acquired by Microsoft"),
    "Take-Two Interactive": ("TTWO", "NASDAQ", "USD", "", "", ""),
    "Ubisoft": ("UBI.PA", "Euronext Paris", "EUR", "", "", ""),
    "Square Enix Holdings": ("9684.T", "Tokyo", "JPY", "", "", ""),
    "Capcom": ("9697.T", "Tokyo", "JPY", "", "", ""),
    "Bandai Namco Holdings": ("7832.T", "Tokyo", "JPY", "", "", ""),
    "Sega Sammy Holdings": ("6460.T", "Tokyo", "JPY", "", "", ""),
    "Konami Group": ("9766.T", "Tokyo", "JPY", "", "", ""),
    "Koei Tecmo Holdings": ("3635.T", "Tokyo", "JPY", "", "", ""),
    "Kadokawa": ("9468.T", "Tokyo", "JPY", "2014-10-01", "",
                 "Listed as Kadokawa Dwango from Oct 2014"),
    "CyberAgent": ("4751.T", "Tokyo", "JPY", "", "", ""),
    "DeNA": ("2432.T", "Tokyo", "JPY", "", "", ""),
    "Nexon": ("3659.T", "Tokyo", "JPY", "", "", ""),
    "Marvelous": ("7844.T", "Tokyo", "JPY", "", "", ""),
    "Tencent": ("0700.HK", "Hong Kong", "HKD", "", "", ""),
    "Kingsoft": ("3888.HK", "Hong Kong", "HKD", "", "", ""),
    "NetEase": ("NTES", "NASDAQ", "USD", "", "",
                "Nasdaq is NetEase's original listing; it also trades as 9999.HK since 2020"),
    "Perfect World": ("002624.SZ", "Shenzhen", "CNY", "", "", ""),
    "Krafton": ("259960.KS", "Korea (KOSPI)", "KRW", "2021-08-10", "", "IPO Aug 2021"),
    "Netmarble": ("251270.KS", "Korea (KOSPI)", "KRW", "2017-05-12", "", ""),
    "Shift Up": ("462870.KS", "Korea (KOSPI)", "KRW", "2024-07-11", "", "IPO Jul 2024"),
    "Neowiz": ("095660.KQ", "Korea (KOSDAQ)", "KRW", "", "", ""),
    "Pearl Abyss": ("263750.KQ", "Korea (KOSDAQ)", "KRW", "", "", ""),
    "CD Projekt": ("CDR.WA", "Warsaw", "PLN", "", "", ""),
    "11 bit studios": ("11B.WA", "Warsaw", "PLN", "", "", ""),
    "Bloober Team": ("BLO.WA", "Warsaw", "PLN", "", "", ""),
    "Remedy Entertainment": ("REMEDY.HE", "Nasdaq Helsinki", "EUR", "2017-05-01", "",
                             "Listed on First North May 2017; main market 2018"),
    "Paradox Interactive": ("PDX.ST", "Nasdaq Stockholm", "SEK", "2016-05-31", "", ""),
    "Embracer Group": ("EMBRAC-B.ST", "Nasdaq Stockholm", "SEK", "", "",
                       "Remaining business being renamed Fellowship Entertainment after the 2025 Coffee Stain spin-off; check ticker"),
    "Thunderful Group": ("THUNDR.ST", "Nasdaq Stockholm", "SEK", "2020-12-07", "2026-02-24",
                         "Acquired by Atari; last trading day 24 Feb 2026"),
    "Digital Bros": ("DIB.MI", "Borsa Italiana", "EUR", "", "", ""),
    "Pullup Entertainment": ("ALPUL.PA", "Euronext Growth Paris", "EUR", "", "",
                             "Formerly Focus Home Interactive / Focus Entertainment (ALFOC); renamed Apr 2024"),
    "Don't Nod": ("ALDNE.PA", "Euronext Growth Paris", "EUR", "2018-04-01", "", ""),
    "Atari SA": ("ALATA.PA", "Euronext Growth Paris", "EUR", "", "", ""),
    "Devolver Digital": ("DEVO.L", "London AIM", "GBP", "2021-11-08", "", "IPO Nov 2021"),
    "Everplay Group": ("EVPL.L", "London AIM", "GBP", "2018-05-23", "",
                       "Formerly Team17 Group (TM17); renamed Everplay"),
    "Frontier Developments": ("FDEV.L", "London AIM", "GBP", "", "", ""),
    "Codemasters Group": ("CDM.L", "London AIM", "GBP", "2018-06-01", "2021-02-18",
                          "Acquired by EA"),
    "Time Warner": ("TWX", "NYSE", "USD", "", "2018-06-14", "Acquired by AT&T"),
    "AT&T": ("T", "NYSE", "USD", "", "", "Owned WarnerMedia Jun 2018 - Apr 2022"),
    "Warner Bros. Discovery": ("WBD", "NASDAQ", "USD", "2022-04-08", "", ""),
    "Walt Disney": ("DIS", "NYSE", "USD", "", "", ""),
    "Meta Platforms": ("META", "NASDAQ", "USD", "", "", "Ticker was FB before Jun 2022"),
    "Alphabet": ("GOOGL", "NASDAQ", "USD", "", "", ""),
    "Amazon": ("AMZN", "NASDAQ", "USD", "", "", ""),
    "Netflix": ("NFLX", "NASDAQ", "USD", "", "", ""),
    "tinyBuild": ("TBLD.L", "London AIM", "GBP", "2021-03-08", "", "IPO Mar 2021"),
}

own_df = pd.DataFrame(O, columns=["entity", "parent_company", "valid_from", "valid_to",
                                  "confidence", "note"])
own_df["valid_from"] = pd.to_datetime(own_df["valid_from"])
own_df["valid_to"] = pd.to_datetime(own_df["valid_to"])

def listed_parent(entity, when):
    """Return (parent, ticker) if the entity was owned by a listed company on `when`."""
    rows = own_df[(own_df.entity == entity) & (own_df.valid_from <= when) & (own_df.valid_to >= when)]
    for parent in rows.parent_company:
        if parent not in PARENTS:
            continue
        tk, ex, cur, lf, lt, _ = PARENTS[parent]
        if lf and pd.Timestamp(lf) > when:
            continue
        if lt and pd.Timestamp(lt) < when:
            continue
        return parent, tk
    if not rows.empty:
        return rows.parent_company.iloc[0], ""
    return "", ""

# ---------------------------------------------------------------- build key
g = awards[awards.category_type == "game"].copy()
g["game"] = g["game"].replace(ALIASES)
g["is_people_credit"] = [(c, y) in PEOPLE_CREDIT_ROWS for c, y in zip(g.category, g.year)]
company = g[~g.is_people_credit & (g.credits != "")]

def pick_credit(s):
    vc = s.value_counts()
    with_pub = [c for c in vc.index if " / " in c]
    return with_pub[0] if with_pub else vc.index[0]

credit = company.groupby("game").credits.agg(pick_credit)
CREDIT_OVERRIDE = {
    "13 Sentinels: Aegis Rim": "Vanillaware / Atlus",
    "Child of Light": "Ubisoft Montreal / Ubisoft",
    "Metal: Hellsinger": "The Outsiders / Funcom",
    "Nier Replicant ver.1.22474487139...": "Toylogic / Square Enix",
}
for t, c in CREDIT_OVERRIDE.items():
    credit.loc[t] = c
first = g.groupby("game").agg(first_year=("year", "min"), last_year=("year", "max"),
                              first_ceremony=("ceremony_date", "min"),
                              nominations=("status", "size"),
                              wins=("status", lambda s: (s == "winner").sum()))
key = first.join(credit.rename("credits")).reset_index()
key["credits"] = key["credits"].fillna("")

devs, pubs, srcs = [], [], []
for t, c in zip(key.game, key.credits):
    if " / " in c:
        d, p = c.split(" / ", 1)
        src = "credited"
    else:
        d, p = c, PUBLISHER_OVERRIDE.get(t, c)
        src = "override" if t in PUBLISHER_OVERRIDE else "self-published (assumed)"
    devs.append("; ".join(split_entities(d)))
    pubs.append("; ".join(split_entities(p)))
    srcs.append(src)
key["developer"], key["publisher"], key["publisher_source"] = devs, pubs, srcs
key["game_id"] = key.game.map(slug)
key["base_game"] = key.game.map(BASE_GAME).fillna(key.game)
key["base_game_id"] = key.base_game.map(slug)
key["aliases"] = key.game.map({v: k for k, v in ALIASES.items()}).fillna("")
key = key.rename(columns={"game": "game_title"})

# ---------------------------------------------------------------- enrich nominations
periods = pd.DataFrame(PUBLISHER_PERIODS, columns=["game_title", "publisher", "valid_from",
                                                   "valid_to", "note"])
periods["valid_from"] = pd.to_datetime(periods.valid_from)
periods["valid_to"] = pd.to_datetime(periods.valid_to)

def resolve(entity_list, when):
    """First entity in the list that had a listed parent on `when`."""
    fallback = ("", "", "")
    for e in [x.strip() for x in entity_list.split(";") if x.strip()]:
        parent, tk = listed_parent(e, when)
        if tk:
            return e, parent, tk
        if not fallback[0]:
            fallback = (e, parent, "")
    return fallback

kmap = key.set_index("game_title")
rows = []
for r in g.itertuples():
    k = kmap.loc[r.game]
    pub = k.publisher
    per = periods[(periods.game_title == r.game) & (periods.valid_from <= r.ceremony_date)
                  & (periods.valid_to >= r.ceremony_date)]
    if not per.empty:
        pub = per.publisher.iloc[0]
    pe, pp, pt = resolve(pub, r.ceremony_date)
    de, dp, dt = resolve(k.developer, r.ceremony_date)
    rows.append({
        "year": r.year, "ceremony_date": r.ceremony_date.date(), "category": r.category,
        "category_std": r.category_std, "game_id": k.game_id, "game_title": r.game,
        "base_game_id": k.base_game_id, "status": r.status, "withdrawn": r.withdrawn,
        "publisher_entity": pe, "publisher_parent": pp, "publisher_ticker": pt,
        "developer_entity": de, "developer_parent": dp, "developer_ticker": dt,
    })
enriched = pd.DataFrame(rows)

# Ticker of the publisher parent at each game's first nomination (handy for the key table)
first_nom = enriched.sort_values("ceremony_date").groupby("game_id").first()
key = key.merge(first_nom[["publisher_parent", "publisher_ticker", "developer_parent",
                           "developer_ticker"]], left_on="game_id", right_index=True, how="left")
key = key.rename(columns={"publisher_parent": "publisher_parent_at_first_nom",
                          "publisher_ticker": "publisher_ticker_at_first_nom",
                          "developer_parent": "developer_parent_at_first_nom",
                          "developer_ticker": "developer_ticker_at_first_nom"})
key["release_date"] = ""  # filled later by a local script (Wikidata / Steam)
key = key[["game_id", "game_title", "aliases", "base_game_id", "base_game", "developer", "publisher",
           "publisher_source", "publisher_parent_at_first_nom", "publisher_ticker_at_first_nom",
           "developer_parent_at_first_nom", "developer_ticker_at_first_nom", "first_year",
           "last_year", "nominations", "wins", "release_date"]].sort_values("game_title")

parents = pd.DataFrame([(p, *v) for p, v in PARENTS.items()],
                       columns=["parent_company", "ticker", "exchange", "currency",
                                "listed_from", "listed_to", "note"])
own_out = own_df.copy()
own_out["valid_from"] = own_out.valid_from.dt.date.astype(str).replace("1900-01-01", "")
own_out["valid_to"] = own_out.valid_to.dt.date.astype(str).replace("2099-12-31", "")
per_out = periods.copy()
per_out["valid_to"] = per_out.valid_to.dt.date.astype(str).replace("2099-12-31", "")
per_out["valid_from"] = per_out.valid_from.dt.date.astype(str)

key.to_csv(OUT / "game_key.csv", index=False, encoding="utf-8-sig")
own_out.to_csv(OUT / "entity_ownership.csv", index=False, encoding="utf-8-sig")
parents.to_csv(OUT / "parent_companies.csv", index=False, encoding="utf-8-sig")
per_out.to_csv(OUT / "publisher_periods.csv", index=False, encoding="utf-8-sig")
enriched.to_csv(OUT / "nominations_enriched.csv", index=False, encoding="utf-8-sig")
print("games:", len(key), "| nominations:", len(enriched))
