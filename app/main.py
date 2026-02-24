"""
FastAPI Application Factory

This module creates and configures the FastAPI application instance.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.storage.db import init_db, get_stock_basic_count
from src.scheduler.manager import scheduler_manager
from src.services.itick_ws_gateway import itick_stock_ws_gateway

from app.routers import (
    health_router, auth_router, settings_router, funds_router,
    stocks_router, market_router, reports_router, commodities_router,
    sentiment_router, dashboard_router, widgets_router, news_router,
    recommendations_router, assistant_router, preferences_router,
    details_router, compare_router, alerts_router, admin_router,
    generate_router, portfolios_router
)
from app.static import setup_static_files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("=" * 50)
    print("VAlpha Terminal API Server Starting...")
    print("=" * 50)

    # Initialize database
    init_db()
    print("[OK] Database initialized")

    # Check if stock_basic needs syncing
    stock_count = get_stock_basic_count()
    if stock_count == 0:
        print("[INFO] Stock basic table is empty. Run /api/admin/sync-stock-basic to populate.")
    else:
        print(f"[OK] Stock basic table has {stock_count} records")

    # Start scheduler
    scheduler_manager.start()
    print("[OK] Scheduler started")

    # Refresh dashboard cache in background
    try:
        loop = asyncio.get_running_loop()

        async def refresh_cache():
            from app.core.config import REPORT_DIR
            from src.analysis.dashboard import DashboardService
            try:
                await loop.run_in_executor(
                    None,
                    DashboardService(REPORT_DIR).get_full_dashboard
                )
                print("[OK] Dashboard cache initialized")
            except Exception as e:
                print(f"[WARN] Dashboard cache init failed: {e}")

        asyncio.create_task(refresh_cache())
    except Exception as e:
        print(f"[WARN] Could not start background tasks: {e}")

    print("=" * 50)
    print("Server ready to accept connections")
    print("=" * 50)

    yield  # Server is running

    # Shutdown
    print("Shutting down...")
    await itick_stock_ws_gateway.stop()
    scheduler_manager.shutdown()
    print("[OK] Scheduler stopped")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="VAlpha Terminal API",
        description="Financial intelligence platform for Chinese market analysis",
        version="2.0.0",
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers in order of specificity
    # Health check (no prefix)
    app.include_router(health_router)

    # Auth
    app.include_router(auth_router)

    # Settings
    app.include_router(settings_router)

    # Core data management
    app.include_router(funds_router)
    app.include_router(stocks_router)
    app.include_router(market_router)
    app.include_router(reports_router)

    # Analysis
    app.include_router(commodities_router)
    app.include_router(sentiment_router)

    # Dashboard & widgets
    app.include_router(dashboard_router)
    app.include_router(widgets_router)

    # News & recommendations
    app.include_router(news_router)
    app.include_router(recommendations_router)

    # AI assistant
    app.include_router(assistant_router)

    # User preferences
    app.include_router(preferences_router)

    # Details & comparison
    app.include_router(details_router)
    app.include_router(compare_router)

    # Alerts
    app.include_router(alerts_router)

    # Admin
    app.include_router(admin_router)

    # Generation
    app.include_router(generate_router)

    # Portfolios (largest router, includes all portfolio-related endpoints)
    app.include_router(portfolios_router)

    # Static files and SPA routing - MUST be last
    setup_static_files(app)

    return app


# Create the application instance
app = create_app()
