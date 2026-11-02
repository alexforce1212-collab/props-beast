import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

print("=== STARTUP ENV CHECK ===")
print(f"ODDS_API_KEY exists: {bool(os.getenv('ODDS_API_KEY'))}")
print(f"ODDS_API_KEY len: {len(os.getenv('ODDS_API_KEY',''))}")
print(f"All env keys containing ODDS: {[k for k in os.environ.keys() if 'ODDS' in k.upper()]}")
print(f"PORT: {os.getenv('PORT')}")
print("=========================")

app = FastAPI(title="BEAST Top Performers Live")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    idx = os.path.join("static", "index.html")
    if os.path.exists(idx):
        return FileResponse(idx, media_type="text/html")
    return {"status": "LIVE", "ui": "/static/index.html", "health": "/api/v1/health", "debug": {"odds_key_set": bool(os.getenv("ODDS_API_KEY")), "odds_key_len": len(os.getenv("ODDS_API_KEY",""))}}

@app.get("/health")
@app.get("/api/v1/health")
def health():
    key = os.getenv("ODDS_API_KEY", "")
    # also check for common typos
    return {
        "live": True, 
        "odds_api_key_set": bool(key.strip()),
        "odds_key_len": len(key.strip()),
        "odds_key_first4": key.strip()[:4] + "..." if key.strip() else None,
        "env_vars_with_odds": [k for k in os.environ.keys() if "ODDS" in k.upper()],
        "check": "If false, add ODDS_API_KEY in Railway Variables and REDEPLOY (not just save)"
    }

@app.get("/api/v1/top-performers")
def top_performers_api(sport: str = Query("all"), mode: str = Query("overall")):
    # import inside so fresh env read
    from top_performers import get_top_performers, get_top_per_team
    sport = sport.lower()
    if mode == "top_per_team":
        return get_top_per_team(sport)
    return get_top_performers(sport)

@app.get("/api/v1/teams")
def teams_api(sport: str = Query("all")):
    from top_performers import get_teams
    return get_teams(sport.lower())

@app.get("/api/v1/team/{team_name}")
def team_detail_api(team_name: str, sport: str = Query("nba")):
    from top_performers import get_team_players
    return get_team_players(team_name, sport.lower())


@app.get("/api/v1/test-odds")
def test_odds():
    import requests
    key = os.getenv("ODDS_API_KEY","").strip()
    if not key:
        return {"error": "ODDS_API_KEY not set", "env_vars": [k for k in os.environ.keys() if "ODDS" in k.upper()]}
    # Test with a simple call that always works - list sports
    try:
        url = "https://api.the-odds-api.com/v4/sports"
        r = requests.get(url, params={"apiKey": key}, timeout=10)
        return {
            "key_set": True,
            "key_len": len(key),
            "key_first4": key[:4]+"...",
            "sports_endpoint_status": r.status_code,
            "sports_count": len(r.json()) if r.status_code==200 else 0,
            "response_preview": str(r.text)[:500],
            "credits_remaining": r.headers.get("x-requests-remaining"),
            "credits_used": r.headers.get("x-requests-used")
        }
    except Exception as e:
        return {"error": str(e), "key_set": bool(key)}

@app.get("/api/v1/test-props/{sport}")
def test_props(sport: str):
    import requests
    key = os.getenv("ODDS_API_KEY","").strip()
    sport_keys = {"nfl": "americanfootball_nfl", "nba": "basketball_nba", "nhl": "icehockey_nhl"}
    sk = sport_keys.get(sport.lower(), "americanfootball_nfl")
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{sk}/odds"
        params = {"apiKey": key, "regions": "us", "markets": "player_pass_yds", "oddsFormat": "american"}
        r = requests.get(url, params=params, timeout=12)
        return {
            "sport": sport,
            "sport_key": sk,
            "status": r.status_code,
            "games": len(r.json()) if r.status_code==200 else 0,
            "credits_remaining": r.headers.get("x-requests-remaining"),
            "preview": str(r.text)[:1000]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/debug-env")
def debug_env():
    # show all env var names (not values) to help user find typo
    return {
        "all_env_names": list(os.environ.keys()),
        "odds_related": [k for k in os.environ.keys() if "ODD" in k.upper() or "API" in k.upper()],
        "odds_key_present": bool(os.getenv("ODDS_API_KEY")),
        "odds_key_len": len(os.getenv("ODDS_API_KEY","").strip())
    }
