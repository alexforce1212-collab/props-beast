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

@app.get("/api/v1/debug-env")
def debug_env():
    # show all env var names (not values) to help user find typo
    return {
        "all_env_names": list(os.environ.keys()),
        "odds_related": [k for k in os.environ.keys() if "ODD" in k.upper() or "API" in k.upper()],
        "odds_key_present": bool(os.getenv("ODDS_API_KEY")),
        "odds_key_len": len(os.getenv("ODDS_API_KEY","").strip())
    }
