import os
print("=== STARTUP ENV CHECK ===")
print(f"ODDS_API_KEY exists: {bool(os.getenv('ODDS_API_KEY'))}")
print(f"ODDS_API_KEY len: {len(os.getenv('ODDS_API_KEY',''))}")
print(f"PORT: {os.getenv('PORT')}")
print("=========================")

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="BEAST Top Performers Live")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir("static"):
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    except Exception as e:
        print(f"Static mount failed: {e}")

@app.get("/")
def root():
    idx = os.path.join("static", "index.html")
    if os.path.exists(idx):
        return FileResponse(idx, media_type="text/html")
    return {"status": "LIVE", "ui": "/static/index.html", "health": "/api/v1/health"}

@app.get("/health")
@app.get("/api/v1/health")
def health():
    key = os.getenv("ODDS_API_KEY", "").strip()
    return {"live": True, "odds_api_key_set": bool(key), "odds_key_len": len(key)}

@app.get("/api/v1/top-performers")
def top_performers_api(sport: str = Query("all"), mode: str = Query("overall")):
    try:
        from top_performers import get_top_performers, get_top_per_team
        sport = sport.lower()
        if mode == "top_per_team":
            return get_top_per_team(sport)
        return get_top_performers(sport)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "data": []}

@app.get("/api/v1/teams")
def teams_api(sport: str = Query("all")):
    try:
        from top_performers import get_teams
        return get_teams(sport.lower())
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v1/team/{team_name}")
def team_detail_api(team_name: str, sport: str = Query("nba")):
    try:
        from top_performers import get_team_players
        return get_team_players(team_name, sport.lower())
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v1/test-odds")
def test_odds():
    import requests
    key = os.getenv("ODDS_API_KEY","").strip()
    if not key:
        return {"error": "ODDS_API_KEY not set"}
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": key}, timeout=10)
        return {"key_set": True, "key_len": len(key), "status": r.status_code, "remaining": r.headers.get("x-requests-remaining"), "preview": r.text[:500]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v1/debug-env")
def debug_env():
    return {"odds_key_present": bool(os.getenv("ODDS_API_KEY")), "env_with_odds": [k for k in os.environ.keys() if "ODDS" in k.upper()]}
