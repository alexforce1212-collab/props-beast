import os
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

# mount static folder at /static - Railway serves files fast, not via python
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    # FAST path - no FileResponse if file is huge, redirect to /static/index.html
    idx = os.path.join("static", "index.html")
    if os.path.exists(idx):
        # serve via redirect to static - avoids python blocking
        return FileResponse(idx, media_type="text/html")
    return {"status": "LIVE", "ui": "/static/index.html", "api": "/api/v1/health"}

@app.get("/health")
@app.get("/api/v1/health")
def health():
    return {"live": True, "odds_api_key_set": bool(os.getenv("ODDS_API_KEY"))}

# lazy import inside endpoint so container starts instantly
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
