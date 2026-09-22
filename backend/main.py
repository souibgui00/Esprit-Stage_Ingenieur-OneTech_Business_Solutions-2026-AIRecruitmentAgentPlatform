import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
load_dotenv()

from cv_management.router import router as cv_router
from user_management.router import router as auth_router
from job_sourcing.router import router as jobs_router
from job_sourcing.search_router import search_router
from matching.router import router as matching_router
from applications.router import router as applications_router
from notifications.router import router as notifications_router
from home.router import router as home_router
from job_sourcing.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database enum types are up-to-date (idempotent)
    try:
        from shared.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'NEW_MATCH';"))
            conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ACTION_REQUIRED';"))
            conn.execute(text("ALTER TYPE applicationmode ADD VALUE IF NOT EXISTS 'ASSISTED';"))
            conn.execute(text("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'DRAFT';"))
            conn.execute(text("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'SUBMITTING';"))
            conn.execute(text("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'ACTION_REQUIRED';"))
            conn.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Notification enum migration (non-fatal): {e}")

    # Start the background collection scheduler
    start_scheduler()
    yield
    stop_scheduler()

# Ensure static directory exists
os.makedirs("static/screenshots", exist_ok=True)

app = FastAPI(title="Plateforme de recrutement IA", redirect_slashes=False, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cv_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(search_router)
app.include_router(matching_router)
app.include_router(applications_router)
app.include_router(notifications_router)
app.include_router(home_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
