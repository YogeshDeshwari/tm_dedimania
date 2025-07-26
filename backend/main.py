from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Trackmania Dedimania Stats API"}

@app.get("/player")
def get_player(login: str = Query(..., description="Dedimania login name")):
    url = "http://dedimania.net/tmstats/?do=stat"
    params = {
        "RGame": "TMU",
        "Login": login,
        "Show": "RECORDS"
    }
    resp = requests.get(url, params=params)
    return JSONResponse(content={"raw_html": resp.text}) 