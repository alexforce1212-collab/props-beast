import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from top_performers import get_api_key, mask_key, check_api_key

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
    idx = os.path.join("static", "index.html")
    if os.path.exists(idx):
        return FileResponse(idx, media_type="text/html")
    return {"status": "LIVE", "service": "BEAST", "ui": "/static/index.html", "health": "/api/v1/health"}

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
