"""
AIDE-X: Autonomous GenAI Decision Engine
Main FastAPI Application Entry Point
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn

from routes import workflow_router, tasks_router, health_router
from database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("aide_x.log")
    ]
)
logger = logging.getLogger("AIDE-X")

# Initialize FastAPI app
app = FastAPI(
    title="AIDE-X: Autonomous GenAI Decision Engine",
    description="Converts natural language requests into structured workflows and executes them automatically.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(workflow_router, prefix="/api/workflow", tags=["Workflow"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["Tasks"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("AIDE-X starting up...")
    init_db()
    logger.info("Database initialized successfully.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AIDE-X shutting down.")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)