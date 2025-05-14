import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from routes.api import api_router 
from routes.docs import docs_html_content 

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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# Include API routes
app.include_router(api_router, prefix="/api") # Added a /api prefix for clarity

# Serve custom HTML documentation at the root
@app.get("/", response_class=HTMLResponse, tags=["Documentation"])
async def get_custom_documentation():
    """
    Serves the custom HTML API documentation page.
    """
    return HTMLResponse(content=docs_html_content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8989))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)