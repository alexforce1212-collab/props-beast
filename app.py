import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from top_performers import get_top_performers, get_top_per_team, get_team_players, get_teams, TEAMS

app = FastAPI(title="BEAST Top Performers Live")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "LIVE",
        "service": "BEAST Top Performers",
        "total_teams": sum(len(v) for v in TEAMS.values()),
        "sports": list(TEAMS.keys())
    }

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
def team_detail_api(team_name: str, sport: str = Query("【entity-nba¦canonical_name=NBA】")):
    return get_team_players(team_name, sport.lower())

@app.get("/api/v1/health")
def health():
    return {"live": True, "odds_api_key_set": bool(os.getenv("ODDS_API_KEY"))}
