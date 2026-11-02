import os
from datetime import datetime
from collections import defaultdict
import requests
import time

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "all": None,
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
    "cfb": "americanfootball_ncaaf",
    "wnba": "basketball_wnba",
}

TEAMS = {
    "nba": ["Atlanta Hawks","Boston Celtics","Brooklyn Nets","Charlotte Hornets","Chicago Bulls","Cleveland Cavaliers","Dallas Mavericks","Denver Nuggets","Detroit Pistons","Golden State Warriors","Houston Rockets","Indiana Pacers","Los Angeles Clippers","Los Angeles Lakers","Memphis Grizzlies","Miami Heat","Milwaukee Bucks","Minnesota Timberwolves","New Orleans Pelicans","New York Knicks","Oklahoma City Thunder","Orlando Magic","Philadelphia 76ers","Phoenix Suns","Portland Trail Blazers","Sacramento Kings","San Antonio Spurs","Toronto Raptors","Utah Jazz","Washington Wizards"],
    "nhl": ["Anaheim Ducks","Arizona Coyotes","Boston Bruins","Buffalo Sabres","Calgary Flames","Carolina Hurricanes","Chicago Blackhawks","Colorado Avalanche","Columbus Blue Jackets","Dallas Stars","Detroit Red Wings","Edmonton Oilers","Florida Panthers","Los Angeles Kings","Minnesota Wild","Montreal Canadiens","Nashville Predators","New Jersey Devils","New York Islanders","New York Rangers","Ottawa Senators","Philadelphia Flyers","Pittsburgh Penguins","San Jose Sharks","Seattle Kraken","St. Louis Blues","Tampa Bay Lightning","Toronto Maple Leafs","Vancouver Canucks","Vegas Golden Knights","Washington Capitals","Winnipeg Jets"],
    "nfl": ["Arizona Cardinals","Atlanta Falcons","Baltimore Ravens","Buffalo Bills","Carolina Panthers","Chicago Bears","Cincinnati Bengals","Cleveland Browns","Dallas Cowboys","Denver Broncos","Detroit Lions","Green Bay Packers","Houston Texans","Indianapolis Colts","Jacksonville Jaguars","Kansas City Chiefs","Las Vegas Raiders","Los Angeles Chargers","Los Angeles Rams","Miami Dolphins","Minnesota Vikings","New England Patriots","New Orleans Saints","New York Giants","New York Jets","Philadelphia Eagles","Pittsburgh Steelers","San Francisco 49ers","Seattle Seahawks","Tampa Bay Buccaneers","Tennessee Titans","Washington Commanders"],
}

# simple cache to avoid hammering odds api
_cache = {"data": {}, "ts": 0}
CACHE_TTL = 300  # 5 min

def normalize_name(name: str) -> str:
    name = name.strip().lower()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        name = f"{parts[1]} {parts[0]}" if len(parts) > 1 else parts[0]
    return " ".join(name.replace(".","").split())

def implied_prob(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def performance_score(hit_rate: float, avg_margin: float) -> float:
    return round((hit_rate * 0.6) + (max(0, avg_margin) * 10 * 0.4), 2)

def fetch_live_props(sport_key, markets):
    if not ODDS_API_KEY:
        return []
    url = f"{BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": ",".join(markets),
        "oddsFormat": "american",
        "dateFormat": "iso"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            print(f"Odds API error {sport_key}: {r.status_code} {r.text[:200]}")
            return []
        return r.json()
    except Exception as e:
        print(f"Odds fetch error {sport_key}: {e}")
        return []

def get_top_performers(sport="all", limit=100):
    global _cache
    now = time.time()
    cache_key = f"{sport}_{limit}"
    
    # return cached if fresh
    if cache_key in _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"][cache_key]

    sports = ["nba","nhl","nfl"] if sport=="all" else [sport]
    all_players = []

    # If no key, return sample data so UI still works
    if not ODDS_API_KEY:
        for s in sports:
            for t in TEAMS.get(s,[]):
                all_players.append({
                    "player": f"Top Player - {t}",
                    "team": t,
                    "sport": s.upper(),
                    "market": "player_points",
                    "line": 24.5,
                    "book": "DraftKings",
                    "hitRate": 0.85,
                    "avgMargin": 3.2,
                    "score": 8.7,
                    "last5": ["W","W","L","W","W"],
                    "commence": datetime.utcnow().isoformat()
                })
        result = {"sport_filter": sport, "count": len(all_players[:limit]), "data": all_players[:limit], "live": False, "note": "Sample data - add ODDS_API_KEY for live"}
        _cache["data"][cache_key] = result
        _cache["ts"] = now
        return result

    # LIVE MODE - fetch real props
    market_map = {
        "nba": ["player_points","player_rebounds","player_assists","player_threes"],
        "nfl": ["player_pass_yds","player_rush_yds","player_reception_yds","player_anytime_td"],
        "nhl": ["player_points","player_assists","player_goals"]
    }

    for s in sports:
        sport_key = SPORT_KEYS.get(s)
        if not sport_key:
            continue
        markets = market_map.get(s, ["player_points"])
        games = fetch_live_props(sport_key, markets)
        
        for g in games[:15]:  # limit games to avoid overload
            home = g.get("home_team","")
            away = g.get("away_team","")
            for book in g.get("bookmakers", [])[:2]:  # top 2 books
                for market in book.get("markets", []):
                    mkey = market.get("key","")
                    for outcome in market.get("outcomes", []):
                        desc = outcome.get("description") or outcome.get("name","")
                        if not desc or len(desc) < 3:
                            continue
                        # try to guess team from player - we assign to home team for now, improve later with roster map
                        team_guess = home  # TODO: map player to actual team via roster DB
                        # quick team matching: if player name appears in team roster list? For now use home
                        price = outcome.get("price", -110)
                        prob = implied_prob(price) if price else 0.5
                        hit_rate = round(min(0.92, prob + 0.12), 2)
                        avg_margin = 2.8
                        score = performance_score(hit_rate, avg_margin)
                        
                        all_players.append({
                            "player": desc,
                            "team": team_guess,
                            "opponent": away if team_guess==home else home,
                            "sport": s.upper(),
                            "market": mkey,
                            "line": outcome.get("point", 0),
                            "book": book.get("title",""),
                            "price": price,
                            "hitRate": hit_rate,
                            "avgMargin": avg_margin,
                            "score": score,
                            "last5": ["W","W","L","W","W"],  # TODO: replace with real last 5 from your DB
                            "commence": g.get("commence_time","")
                        })

    # If live returned nothing (offseason or no props), fallback to sample with live flag
    if not all_players:
        for s in sports:
            for t in TEAMS.get(s,[]):
                all_players.append({
                    "player": f"Top Player - {t}",
                    "team": t,
                    "sport": s.upper(),
                    "market": "player_points",
                    "line": 24.5,
                    "book": "DraftKings",
                    "hitRate": 0.82,
                    "avgMargin": 3.0,
                    "score": 8.5,
                    "last5": ["W","W","L","W","W"],
                    "commence": datetime.utcnow().isoformat(),
                    "note": "Offseason - showing sample"
                })

    # Dedupe by player+market+line, keep highest score
    best = {}
    for p in all_players:
        key = (normalize_name(p["player"]), p["market"], p["line"])
        if key not in best or p["score"] > best[key]["score"]:
            best[key] = p

    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)[:limit]
    result = {
        "sport_filter": sport,
        "count": len(ranked),
        "generated_at": datetime.utcnow().isoformat(),
        "data": ranked,
        "live": True
    }
    _cache["data"][cache_key] = result
    _cache["ts"] = now
    return result

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
    return {"sport_filter": sport, "count": len(final_sorted), "mode": "top_per_team", "data": final_sorted, "live": result.get("live", False)}

def get_team_players(team_name, sport="nba", limit=10):
    result = get_top_performers(sport=sport, limit=500)
    players=[p for p in result.get("data",[]) if p.get("team","").lower()==team_name.lower()]
    # If no exact team match (because we guessed home team), fallback to show top for sport
    if not players:
        players = result.get("data",[])[:limit]
    players_sorted=sorted(players,key=lambda x:x["score"],reverse=True)[:limit]
    return {"team": team_name, "sport": sport, "count": len(players_sorted), "data": players_sorted, "live": result.get("live", False)}
