"""FastAPI application setup."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config.settings import Config
from bot.core import FootballProphet

# Module-level prophet instance
_prophet: Optional[FootballProphet] = None


def get_prophet() -> FootballProphet:
    """Get the global prophet instance."""
    if _prophet is None:
        raise RuntimeError("Prophet not initialized")
    return _prophet


def create_app(config: Optional[Config] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = Config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _prophet
        _prophet = FootballProphet(config)
        await _prophet.initialize()
        yield
        await _prophet.shutdown()
        _prophet = None

    app = FastAPI(
        title="Football Prophet API",
        description="Professional Match Prediction System",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    from api.routes.predictions import router as predictions_router
    from api.routes.matches import router as matches_router
    from api.routes.teams import router as teams_router
    from api.routes.odds import router as odds_router
    from api.routes.dashboard import router as dashboard_router

    app.include_router(predictions_router, prefix="/api")
    app.include_router(matches_router, prefix="/api")
    app.include_router(teams_router, prefix="/api")
    app.include_router(odds_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        html_path = Path(__file__).resolve().parent.parent / "dashboard.html"
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @app.get("/")
    async def root():
        return {
            "name": "Football Prophet",
            "version": "1.0.0",
            "docs": "/docs",
            "dashboard": "/dashboard",
        }

    @app.get("/health")
    async def health():
        prophet = get_prophet()
        return {
            "status": "healthy",
            "brain_loaded": prophet.persistence.state_exists(),
            "teams_tracked": len(prophet.memory.team_profiles),
            "active_predictions": len(prophet.state.active_predictions),
        }

    return app
