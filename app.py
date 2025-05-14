import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8989))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)