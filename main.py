from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

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

# Routes
from routes import (
    analytics_router,
    dashboard_router,
    docs_router,
    pr_router,
    # api_router,
)

app.include_router(docs_router, tags=["Documentation"])
app.include_router(analytics_router, tags=["Analytics"])
app.include_router(dashboard_router, tags=["Dashboard"])
app.include_router(pr_router, tags=["PRs"])
# app.include_router(api_router, tags=["API"])

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8989))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
    )
