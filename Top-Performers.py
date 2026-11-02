
import os, time
from datetime import datetime
from collections import defaultdict
import requests

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

def normalize_name(name: str) -> str:
    # LeBron James vs L. James vs James, LeBron -> lebron james
    name = name.strip().lower()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        name = f"{parts[1]} {parts[0]}" if len(parts) > 1 else parts[0]
    # remove periods from initials: l. james -> l james -> expand later via map
    name = name.replace(".", "")
    return " ".join(name.split())

def implied_prob(american_odds: int) -> float:
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def performance_score(hit_rate: float, avg_margin: float) -> float:
    # 60% hit rate + 40% margin
    return round((hit_rate * 0.6) + (max(0, avg_margin) * 10 * 0.4), 2)

def get_top_performers(sport="all", limit=20):
    """
    Filterable top performers across sports.
    Usage: get_top_performers("nfl") / get_top_performers("all")
    """
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not set in environment", "data": []}

    sports_to_scan = [k for k in SPORT_KEYS if k != "all"] if sport == "all" else [sport]

    all_players = []

    for s in sports_to_scan:
        sport_key = SPORT_KEYS.get(s)
        if not sport_key:
            continue
        try:
            # Example: player points / props markets - adjust per sport
            url = f"{BASE}/sports/{sport_key}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "player_points,player_rebounds,player_assists,player_pass_yds,player_rush_yds",
                "oddsFormat": "american",
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                continue
            games = r.json()
            # --- Simplified scoring stub: replace with your historical DB ---
            # In production, join with last 5-10 game logs here
            for g in games[:10]:
                for book in g.get("bookmakers", [])[:3]:
                    for market in book.get("markets", []):
                        for outcome in market.get("outcomes", []):
                            name = normalize_name(outcome.get("description", outcome.get("name","")))
                            if not name or len(name) < 3:
                                continue
                            line = outcome.get("point", 0)
                            # Placeholder: compute from your DB
                            # For now, mock hit_rate derived from price to show structure
                            price = outcome.get("price", -110)
                            prob = implied_prob(price)
                            # TODO: replace with real last-5 calculation
                            hit_rate = round(min(0.95, prob + 0.15), 2)  # stub
                            avg_margin = 2.5  # stub - replace with real margin
                            score = performance_score(hit_rate, avg_margin)
                            all_players.append({
                                "player": outcome.get("description", outcome.get("name")),
                                "team": g.get("home_team"),
                                "sport": s.upper(),
                                "market": market.get("key"),
                                "line": line,
                                "book": book.get("title"),
                                "hitRate": hit_rate,
                                "avgMargin": avg_margin,
                                "score": score,
                                "commence": g.get("commence_time"),
                            })
        except Exception as e:
            print(f"error {s}: {e}")
            continue

    # Dedupe by normalized player+market, keep highest score
    best = {}
    for p in all_players:
        key = (normalize_name(p["player"]), p["market"], p["line"])
        if key not in best or p["score"] > best[key]["score"]:
            best[key] = p

    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)
    return {
        "sport_filter": sport,
        "count": len(ranked[:limit]),
        "generated_at": datetime.utcnow().isoformat(),
        "data": ranked[:limit]
    }

if __name__ == "__main__":
    import json, sys
    f = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(json.dumps(get_top_performers(f), indent=2))
