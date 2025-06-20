from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import kunden, orte, event

app = FastAPI(title="SkiApp API", version="0.0.1")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kunden.router, prefix="/api/v1")
app.include_router(orte.router, prefix="/api/v1")
app.include_router(event.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"Hello": "World"}



