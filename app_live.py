
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
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

TEAMS = {
    "nba": ["Atlanta Hawks","Boston Celtics","Brooklyn Nets","Charlotte Hornets","Chicago Bulls","Cleveland Cavaliers","Dallas Mavericks","Denver Nuggets","Detroit Pistons","Golden State Warriors","Houston Rockets","Indiana Pacers","Los Angeles Clippers","Los Angeles Lakers","Memphis Grizzlies","Miami Heat","Milwaukee Bucks","Minnesota Timberwolves","New Orleans Pelicans","New York Knicks","Oklahoma City Thunder","Orlando Magic","Philadelphia 76ers","Phoenix Suns","Portland Trail Blazers","Sacramento Kings","San Antonio Spurs","Toronto Raptors","Utah Jazz","Washington Wizards"],
    "nhl": ["Anaheim Ducks","Arizona Coyotes","Boston Bruins","Buffalo Sabres","Calgary Flames","Carolina Hurricanes","Chicago Blackhawks","Colorado Avalanche","Columbus Blue Jackets","Dallas Stars","Detroit Red Wings","Edmonton Oilers","Florida Panthers","Los Angeles Kings","Minnesota Wild","Montreal Canadiens","Nashville Predators","New Jersey Devils","New York Islanders","New York Rangers","Ottawa Senators","Philadelphia Flyers","Pittsburgh Penguins","San Jose Sharks","Seattle Kraken","St. Louis Blues","Tampa Bay Lightning","Toronto Maple Leafs","Vancouver Canucks","Vegas Golden Knights","Washington Capitals","Winnipeg Jets"],
    "nfl": ["Arizona Cardinals","Atlanta Falcons","Baltimore Ravens","Buffalo Bills","Carolina Panthers","Chicago Bears","Cincinnati Bengals","Cleveland Browns","Dallas Cowboys","Denver Broncos","Detroit Lions","Green Bay Packers","Houston Texans","Indianapolis Colts","Jacksonville Jaguars","Kansas City Chiefs","Las Vegas Raiders","Los Angeles Chargers","Los Angeles Rams","Miami Dolphins","Minnesota Vikings","New England Patriots","New Orleans Saints","New York Giants","New York Jets","Philadelphia Eagles","Pittsburgh Steelers","San Francisco 49ers","Seattle Seahawks","Tampa Bay Buccaneers","Tennessee Titans","Washington Commanders"],
}

def normalize_name(name: str) -> str:
    name = name.strip().lower()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        name = f"{parts[1]} {parts[0]}" if len(parts) > 1 else parts[0]
    return " ".join(name.replace(".","").split())

def performance_score(hit_rate: float, avg_margin: float) -> float:
    return round((hit_rate * 0.6) + (max(0, avg_margin) * 10 * 0.4), 2)

def get_top_performers(sport="all", limit=20):
    if not ODDS_API_KEY:
        # return team shells so UI still works without key
        sports = ["nba","nhl","nfl"] if sport=="all" else [sport]
        data=[]
        for s in sports:
            for t in TEAMS.get(s,[]):
                data.append({"player":"Sample Player","team":t,"sport":s.upper(),"market":"player_points","line":24.5,"book":"DraftKings","hitRate":0.82,"avgMargin":3.1,"score":8.5})
        return {"sport_filter": sport, "count": len(data[:limit]), "data": data[:limit], "live": False}
    # ... real odds api logic would go here ...
    return {"sport_filter": sport, "count": 0, "data": [], "live": True}

def get_teams(sport="all"):
    if sport=="all":
        return TEAMS
    return {sport: TEAMS.get(sport, [])}

def get_top_per_team(sport="all", limit_per_team=1):
    result = get_top_performers(sport=sport, limit=500)
    by_team = defaultdict(list)
    for p in result["data"]:
        by_team[(p["team"], p["sport"])].append(p)
    final=[]
    for (team, sp), players in by_team.items():
        players_sorted=sorted(players,key=lambda x:x["score"],reverse=True)
        final.extend(players_sorted[:limit_per_team])
    final_sorted=sorted(final,key=lambda x:x["score"],reverse=True)
    result["data"]=final_sorted
    result["count"]=len(final_sorted)
    result["mode"]="top_per_team"
    return result

def get_team_players(team_name, sport="nba", limit=10):
    result = get_top_performers(sport=sport, limit=500)
    players=[p for p in result.get("data",[]) if p.get("team","").lower()==team_name.lower()]
    players_sorted=sorted(players,key=lambda x:x["score"],reverse=True)[:limit]
    return {"team":team_name,"sport":sport,"count":len(players_sorted),"data":players_sorted}

app = FastAPI(title="BEAST Top Performers Live")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"status":"LIVE","service":"BEAST Top Performers","teams": sum(len(v) for v in TEAMS.values())}

@app.get("/api/v1/top-performers")
def top_performers_api(sport: str = Query("all"), mode: str = Query("overall")):
    if mode=="top_per_team":
        return get_top_per_team(sport.lower())
    return get_top_performers(sport.lower())

@app.get("/api/v1/teams")
def teams_api(sport: str = Query("all")):
    return get_teams(sport.lower())

@app.get("/api/v1/team/{team_name}")
def team_api(team_name: str, sport: str = Query("nba")):
    return get_team_players(team_name, sport.lower())

@app.get("/api/v1/health")
def health():
    return {"live": True, "odds_api_key_set": bool(ODDS_API_KEY)}
