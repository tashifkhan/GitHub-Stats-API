# GitHub Analytics API

This application provides a FastAPI-based service that retrieves and analyzes GitHub user data. It includes endpoints for retrieving programming language statistics and contribution history, including total commits and longest streak.

## Installation

1. Clone the repository.
2. Create and activate a virtual environment.
   ```
   python -m venv .venv
   source .venv/bin/activate # MacOS & Linux
   .\venv\Scripts\Activate   # Windows
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Configure a .env file with your GitHub token:
   ```
   GITHUB_TOKEN=your_personal_access_token
   ```

## Usage

1. Start the FastAPI application:
   ```
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
2. Access the documentation at:
   ```
   http://localhost:8000/docs
   ```

## Endpoints

- GET /{username}/languages  
  Returns top programming languages used by a user.
- GET /{username}/contributions  
  Returns the user's contribution graphs, total commits, and longest streak.
- GET /{username}/stats  
  Combines language stats, total commits, and longest streak into one endpoint.

## License

See [LICENSE](./LICENSE) for details.
