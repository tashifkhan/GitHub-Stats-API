from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from core.middleware import CacheRateLimitMiddleware

app = FastAPI(
    title="GitHub Analytics API",
    description="""
    An API for analyzing GitHub user statistics, including:
    * Language usage statistics
    * Contribution history
    * Commit streaks
    * Overall GitHub activity metrics
    
    Use this API to get detailed insights into GitHub user activity patterns.
    Custom API documentation page available at `/`.
    Interactive Swagger UI available at `/docs`.
    Alternative ReDoc documentation available at `/redoc`.
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "https://github.com/tashifkhan/GitHub-Stats-API",
    },
)

# CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CacheRateLimitMiddleware, platform="github")

# Routes
from routes import (
    analytics_router,
    badges_router,
    docs_router,
    heatmap_router,
    profile_router,
    pr_router,
    summary_router,
    # api_router,
)

app.include_router(docs_router, tags=["Documentation"])
app.include_router(profile_router)
app.include_router(heatmap_router)
app.include_router(badges_router)
app.include_router(summary_router)
app.include_router(analytics_router)
app.include_router(pr_router)
# app.include_router(api_router, tags=["API"])

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8989))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(
        "main:app",
        reload=True,
        host=host,
        port=port,
    )
