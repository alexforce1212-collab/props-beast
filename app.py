import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

try:
    from top_performers import get_top_performers, get_top_per_team, get_team_players, get_teams, TEAMS
except Exception as e:
    print(f"Import error top_performers: {e}")
    TEAMS = {"nba":[],"nhl":[],"nfl":[]}
    def get_top_performers(*a,**k): return {"error": str(e), "data":[]}
    def get_top_per_team(*a,**k): return {"error": str(e), "data":[]}
    def get_team_players(*a,**k): return {"error": str(e), "data":[]}
    def get_teams(*a,**k): return TEAMS

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
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "status": "LIVE",
        "service": "BEAST Top Performers",
        "total_teams": sum(len(v) for v in TEAMS.values()),
        "check": "/api/v1/health"
    }

@app.get("/api")
def api_root():
    return {"status": "LIVE"}

@app.get("/api/v1/top-performers")
def top_performers_api(sport: str = Query("all"), mode: str = Query("overall")):
    try:
        sport = sport.lower()
        if mode == "top_per_team":
            return get_top_per_team(sport)
        return get_top_performers(sport)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/teams")
def teams_api(sport: str = Query("all")):
    try:
        return get_teams(sport.lower())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/team/{team_name}")
def team_detail_api(team_name: str, sport: str = Query("nba")):
    try:
        return get_team_players(team_name, sport.lower())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/health")
def health():
    return {"live": True, "odds_api_key_set": bool(os.getenv("ODDS_API_KEY")), "teams": sum(len(v) for v in TEAMS.values())}

@app.get("/health")
def health2():
    return {"live": True}
