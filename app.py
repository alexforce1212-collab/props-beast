import os
import time
from collections import defaultdict
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    # Loads a local .env file if present (handy when running outside Docker)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Odds API / top performers logic (merged in so the app is a single file)
# ---------------------------------------------------------------------------

BASE = "https://api.the-odds-api.com/v4"

KEY_NAMES = ("ODDS_API_KEY", "THE_ODDS_API_KEY", "API_KEY")

def get_api_key() -> str:
    # Read at call time (not import time) so a key set after startup is still picked up.
    # Strips whitespace and stray quotes, e.g. ODDS_API_KEY="abc123" in a .env or dashboard.
    for name in KEY_NAMES:
        val = os.getenv(name, "").strip().strip('"').strip("'").strip()
        if val:
            return val
    return ""

def mask_key(key: str) -> str:
    if not key:
        return ""
    return f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"

def check_api_key() -> dict:
    # /sports is free and does not use quota, so it's a safe way to validate the key
    key = get_api_key()
    if not key:
        return {"key_set": False, "valid": False, "error": f"None of {', '.join(KEY_NAMES)} is set"}
    try:
        r = requests.get(f"{BASE}/sports", params={"apiKey": key}, timeout=10)
        return {
            "key_set": True,
            "key_preview": mask_key(key),
            "valid": r.status_code == 200,
            "status_code": r.status_code,
            "requests_remaining": r.headers.get("x-requests-remaining"),
            "error": None if r.status_code == 200 else r.text[:300],
        }
    except Exception as e:
        return {"key_set": True, "key_preview": mask_key(key), "valid": False, "error": str(e)}

SPORT_KEYS = {
    "all": None,
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
    "cfb": "americanfootball_ncaaf",
    "wnba": "basketball_wnba",
}

# Player prop market pulled per sport
PROP_MARKETS = {
    "nba": "player_points",
    "wnba": "player_points",
    "nhl": "player_points",
    "nfl": "player_pass_yds",
    "cfb": "player_pass_yds",
    "mlb": "batter_hits",
}

# Each event costs quota, so cap how many games we pull per sport
MAX_EVENTS_PER_SPORT = int(os.getenv("MAX_EVENTS_PER_SPORT", "5"))

TEAMS = {
    "nba": ["Atlanta Hawks","Boston Celtics","Brooklyn Nets","Charlotte Hornets","Chicago Bulls","Cleveland Cavaliers","Dallas Mavericks","Denver Nuggets","Detroit Pistons","Golden State Warriors","Houston Rockets","Indiana Pacers","Los Angeles Clippers","Los Angeles Lakers","Memphis Grizzlies","Miami Heat","Milwaukee Bucks","Minnesota Timberwolves","New Orleans Pelicans","New York Knicks","Oklahoma City Thunder","Orlando Magic","Philadelphia 76ers","Phoenix Suns","Portland Trail Blazers","Sacramento Kings","San Antonio Spurs","Toronto Raptors","Utah Jazz","Washington Wizards"],
    "nhl": ["Anaheim Ducks","Arizona Coyotes","Boston Bruins","Buffalo Sabres","Calgary Flames","Carolina Hurricanes","Chicago Blackhawks","Colorado Avalanche","Columbus Blue Jackets","Dallas Stars","Detroit Red Wings","Edmonton Oilers","Florida Panthers","Los Angeles Kings","Minnesota Wild","Montreal Canadiens","Nashville Predators","New Jersey Devils","New York Islanders","New York Rangers","Ottawa Senators","Philadelphia Flyers","Pittsburgh Penguins","San Jose Sharks","Seattle Kraken","St. Louis Blues","Tampa Bay Lightning","Toronto Maple Leafs","Vancouver Canucks","Vegas Golden Knights","Washington Capitals","Winnipeg Jets"],
    "nfl": ["Arizona Cardinals","Atlanta Falcons","Baltimore Ravens","Buffalo Bills","Carolina Panthers","Chicago Bears","Cincinnati Bengals","Cleveland Browns","Dallas Cowboys","Denver Broncos","Detroit Lions","Green Bay Packers","Houston Texans","Indianapolis Colts","Jacksonville Jaguars","Kansas City Chiefs","Las Vegas Raiders","Los Angeles Chargers","Los Angeles Rams","Miami Dolphins","Minnesota Vikings","New England Patriots","New Orleans Saints","New York Giants","New York Jets","Philadelphia Eagles","Pittsburgh Steelers","San Francisco 49ers","Seattle Seahawks","Tampa Bay Buccaneers","Tennessee Titans","Washington Commanders"],
}

def implied_prob(american: float) -> float:
    if american is None:
        return 0.0
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)

def sample_data(sports, limit, sport, note):
    data=[]
    for s in sports:
        for t in TEAMS.get(s,[]):
            data.append({
                "player": f"Top Player - {t}",
                "team": t,
                "sport": s.upper(),
                "market": "player_points",
                "line": 24.5,
                "book": "DraftKings",
                "hitRate": 0.85,
                "avgMargin": 3.2,
                "score": 8.7,
                "last5": ["W","W","L","W","W"]
            })
    return {"sport_filter": sport, "count": len(data[:limit]), "data": data[:limit], "live": False, "note": note}

MARKET_LABELS = {
    "player_points": "Points",
    "player_pass_yds": "Pass Yds",
    "batter_hits": "Hits",
}

# Cache live results so every page load doesn't burn Odds API quota
CACHE_SECONDS = int(os.getenv("CACHE_SECONDS", "300"))
_cache = {}

def fetch_sport_props(s, sport_key, key, errors):
    players=[]
    market = PROP_MARKETS.get(s)
    if not market:
        return players
    r = requests.get(f"{BASE}/sports/{sport_key}/events", params={"apiKey": key}, timeout=10)
    if r.status_code != 200:
        errors.append(f"{s}: events HTTP {r.status_code} - {r.text[:200]}")
        return players
    for ev in r.json()[:MAX_EVENTS_PER_SPORT]:
        params = {"apiKey": key, "regions": "us", "markets": market, "oddsFormat": "american"}
        er = requests.get(f"{BASE}/sports/{sport_key}/events/{ev['id']}/odds", params=params, timeout=10)
        if er.status_code != 200:
            errors.append(f"{s}: odds HTTP {er.status_code} - {er.text[:200]}")
            continue
        game = f"{ev.get('away_team')} @ {ev.get('home_team')}"
        # (player, line) -> every book's Over price at that line
        quotes = defaultdict(list)
        for bm in er.json().get("bookmakers", []):
            for mk in bm.get("markets", []):
                for oc in mk.get("outcomes", []):
                    if oc.get("name") != "Over" or not oc.get("description") or oc.get("price") is None:
                        continue
                    quotes[(oc["description"], oc.get("point"))].append((bm.get("title"), oc["price"]))
        # Per player, use the line the most books agree on
        by_player = {}
        for (name, point), qs in quotes.items():
            if name not in by_player or len(qs) > len(by_player[name][1]):
                by_player[name] = (point, qs)
        for name, (point, qs) in by_player.items():
            probs = [implied_prob(p) for _, p in qs]
            consensus = sum(probs) / len(probs)
            book, price = min(qs, key=lambda q: implied_prob(q[1]))  # best payout for the bettor
            players.append({
                "player": name,
                "team": game,
                "game": game,
                "home_team": ev.get("home_team"),
                "away_team": ev.get("away_team"),
                "sport": s.upper(),
                "market": market,
                "line": point,
                "price": price,
                "book": book,
                "books": len(qs),
                "hitRate": round(consensus, 3),
                "edge": round((consensus - implied_prob(price)) * 100, 1),
                "avgMargin": 0,
                "score": round(consensus * 100, 1),
                "last5": [],
                "commence_time": ev.get("commence_time"),
            })
    return players

def get_top_performers(sport="all", limit=20):
    sports = ["nba","nhl","nfl"] if sport=="all" else [sport]
    key = get_api_key()
    if not key:
        # Returns sample data when no API key, so UI works immediately
        return sample_data(sports, limit, sport, "Add ODDS_API_KEY env var for live odds")

    cached = _cache.get(sport)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        all_players, errors = cached[1], cached[2]
    else:
        errors=[]
        all_players=[]
        try:
            for s in sports:
                sport_key = SPORT_KEYS.get(s)
                if not sport_key:
                    continue
                all_players.extend(fetch_sport_props(s, sport_key, key, errors))
        except Exception as e:
            errors.append(str(e))
        all_players.sort(key=lambda x: x["score"], reverse=True)
        # Don't cache a total failure, so a fixed key works on the next request
        if all_players or not errors:
            _cache[sport] = (time.time(), all_players, errors)

    result = {"sport_filter": sport, "count": len(all_players[:limit]), "data": all_players[:limit], "live": True}
    if errors:
        result["errors"] = errors
    return result

def get_page_props(sport="all"):
    # Same live data, shaped the way static/index.html renders it
    result = get_top_performers(sport=sport, limit=1000)
    if not result.get("live"):
        return {"live": False, "data": [], "note": result.get("note")}
    data = []
    for p in result["data"]:
        line = p.get("line")
        data.append({
            "name": p["player"],
            "sport": p["sport"],
            "home_team": p["home_team"],
            "away_team": p["away_team"],
            "market": MARKET_LABELS.get(p["market"], p["market"]),
            "line": f"O {line:.1f}" if isinstance(line, (int, float)) else "O —",
            "book": p["book"],
            "hitRate": round(p["hitRate"] * 100),
            "last5": [],
            "score": p["score"],
            "edge": f"{p['edge']:+.1f}%",
        })
    out = {"live": True, "count": len(data), "data": data}
    if result.get("errors"):
        out["errors"] = result["errors"]
    return out

def get_teams(sport="all"):
    if sport=="all":
        return TEAMS
    return {sport: TEAMS.get(sport, [])}

def get_top_per_team(sport="all", limit_per_team=1):
    result = get_top_performers(sport=sport, limit=500)
    by_team = defaultdict(list)
    for p in result.get("data",[]):
        by_team[(p["team"], p["sport"])].append(p)
    final=[]
    for (team, sp), players in by_team.items():
        players_sorted=sorted(players,key=lambda x:x["score"],reverse=True)
        final.extend(players_sorted[:limit_per_team])
    final_sorted=sorted(final,key=lambda x:x["score"],reverse=True)
    out = {"sport_filter": sport, "count": len(final_sorted), "mode": "top_per_team", "data": final_sorted, "live": result.get("live", False)}
    if result.get("errors"):
        out["errors"] = result["errors"]
    return out

def get_team_players(team_name, sport="nba", limit=10):
    result = get_top_performers(sport=sport, limit=500)
    t = team_name.lower()
    # Live data stores the matchup ("Away @ Home"), so match the team inside it
    players=[p for p in result.get("data",[]) if t == p.get("team","").lower() or t in p.get("game","").lower()]
    players_sorted=sorted(players,key=lambda x:x["score"],reverse=True)[:limit]
    return {"team": team_name, "sport": sport, "count": len(players_sorted), "data": players_sorted, "live": result.get("live", False)}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="BEAST Top Performers Live")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def log_key_status():
    key = get_api_key()
    print(f"[BEAST] ODDS_API_KEY {'loaded: ' + mask_key(key) if key else 'NOT SET - serving sample data'}", flush=True)

# FIX: mount at /static ONLY - never at "/"
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    # Linux is case-sensitive, so accept index.html or Index.html
    for fname in ("index.html", "Index.html"):
        idx = os.path.join("static", fname)
        if os.path.exists(idx):
            return FileResponse(idx, media_type="text/html")
    return {"status": "LIVE", "service": "BEAST", "ui": "/static/index.html", "health": "/api/v1/health"}

@app.get("/api/v1/props")
def props_api(sport: str = Query("all")):
    return get_page_props(sport.lower())

@app.get("/health")
@app.get("/api/v1/health")
def health(check: bool = Query(False)):
    key = get_api_key()
    out = {"live": True, "odds_api_key_set": bool(key), "key_preview": mask_key(key)}
    if check:
        out["key_check"] = check_api_key()
    return out

@app.get("/api/v1/top-performers")
def top_performers_api(sport: str = Query("all"), mode: str = Query("overall")):
    sport = sport.lower()
    if mode == "top_per_team":
        return get_top_per_team(sport)
    return get_top_performers(sport)

@app.get("/api/v1/teams")
def teams_api(sport: str = Query("all")):
    return get_teams(sport.lower())

@app.get("/api/v1/team/{team_name}")
def team_detail_api(team_name: str, sport: str = Query("nba")):
    return get_team_players(team_name, sport.lower())
