
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from top_performers import get_top_performers, get_top_per_team, get_team_players, get_teams
import os

app = FastAPI(title="BEAST Top Performers Live")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "LIVE", "service": "BEAST Top Performers", "endpoints": ["/api/v1/top-performers", "/api/v1/teams", "/api/v1/team/{name}"]}

@app.get("/api/v1/top-performers")
def top_performers(sport: str = Query("all"), mode: str = Query("overall")):
    sport=sport.lower()
    if mode=="top_per_team":
        return get_top_per_team(sport, limit_per_team=1)
    return get_top_performers(sport)

@app.get("/api/v1/teams")
def teams(sport: str = Query("all")):
    return get_teams(sport.lower())

@app.get("/api/v1/team/{team_name}")
def team_detail(team_name: str, sport: str = Query("nba")):
    return get_team_players(team_name, sport.lower())

@app.get("/api/v1/health")
def health():
    key_set = bool(os.getenv("ODDS_API_KEY"))
    return {"live": True, "odds_api_key_set": key_set}
