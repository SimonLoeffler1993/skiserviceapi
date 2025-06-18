from fastapi import FastAPI
from app.api.v1 import kunden, orte

app = FastAPI(title="SkiApp API", version="0.0.1")

app.include_router(kunden.router, prefix="/api/v1")
app.include_router(orte.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"Hello": "World"}



