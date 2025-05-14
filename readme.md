# GitHub Stats API

A robust RESTful API built with FastAPI that retrieves and analyzes GitHub user data, including programming language statistics and contribution history.

hosted at ![github-stats.tashif.codes](https://github-stats.tashif.codes)

## Features

- Fetch programming language statistics used by any GitHub user
- Retrieve detailed contribution history and metrics
- View total commits and longest streak information
- Get comprehensive user statistics in a single request
- Interactive API documentation (Swagger UI & ReDoc)
- Custom HTML documentation page
- Easy integration with other applications

### Get Complete Statistics

```
GET /{username}/stats
```

Get comprehensive GitHub statistics for a user, combining top programming languages, total contribution count, and longest contribution streak.

#### Parameters

- `username` (path): GitHub username
- `exclude` (query, optional): Comma-separated list of languages to exclude

#### Response

Returns comprehensive data including top programming languages, total commits, longest streak, and contribution history.

#### Example Response

```json
{
	"topLanguages": [{ "name": "Python", "percentage": 45.0 }],
	"totalCommits": 1234,
	"longestStreak": 30
}
```

### Get Language Statistics

```
GET /{username}/languages
```

Get the programming languages used in a GitHub user's repositories.

#### Parameters

- `username` (path): GitHub username
- `exclude` (query, optional): Comma-separated list of languages to exclude (default: Markdown, JSON, YAML, XML)

#### Response

Returns the user's most frequently used programming languages with usage percentages.

#### Example Response

```json
[
	{ "name": "Python", "percentage": 45.0 },
	{ "name": "JavaScript", "percentage": 30.0 }
]
```

### Get Contribution History

```
GET /{username}/contributions
```

Retrieve a user's GitHub contribution history and statistics, including contribution calendar data, total commits, and longest streak.

#### Parameters

- `username` (path): GitHub username
- `starting_year` (query, optional): Starting year for contribution history (defaults to account creation year)

#### Response

Returns contribution calendar data, total commit count, and longest contribution streak.

#### Example Response

```json
{
	"contributions": {
		"2023": {
			"data": {
				"user": {
					"contributionsCollection": {
						"weeks": []
					}
				}
			}
		},
		"totalCommits": 1234,
		"longestStreak": 30
	}
}
```

### Get Repository Details

```
GET /{username}/repos
```

Retrieves detailed information for each of the user's public repositories.

#### Parameters

- `username` (path): GitHub username

#### Response

Returns a list of repository details.

#### Example Response

```json
[
	{
		"title": "RepoName",
		"description": "A cool project.",
		"live_website_url": "https://example.com",
		"languages": ["Python", "JavaScript"],
		"num_commits": 42,
		"readme": "BASE64_ENCODED_README_CONTENT"
	}
]
```

### Get Commit History

```
GET /{username}/commits
```

Retrieves a list of all commits made by the user across their owned repositories.

#### Parameters

- `username` (path): GitHub username

#### Response

Returns a list of commit details.

#### Example Response

```json
[
	{
		"repo": "RepoName",
		"message": "Fix: A critical bug",
		"timestamp": "2023-01-01T12:00:00Z",
		"sha": "commit_sha_hash",
		"url": "https://github.com/user/repo/commit/sha"
	}
]
```

## API Documentation

- Custom HTML documentation is available at the root endpoint: `/`
- Interactive Swagger UI documentation is available at: `/docs`
- Alternative ReDoc documentation is available at: `/redoc`

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Request successful
- `404 Not Found`: User not found on GitHub
- `500 Internal Server Error`: GitHub token configuration error

Error responses follow this format:

```json
{
	"status": "error",
	"message": "Error description",
	"topLanguages": [],
	"totalCommits": 0,
	"longestStreak": 0,
	"repos": [],
	"commits": []
}
```

## Usage Examples

### Python

```python
import requests

username = "octocat"
# Update base URL if running locally, e.g., http://localhost:8000
base_url = "https://github-stats.tashif.codes" # Or your deployed URL
response = requests.get(f"{base_url}/{username}/stats")
data = response.json()

print(f"{username} has made {data['totalCommits']} commits with a longest streak of {data['longestStreak']} days!")
```

### JavaScript

```javascript
const username = "octocat";
// Update base URL if running locally, e.g., http://localhost:8000
const baseUrl = "https://github-stats.tashif.codes"; // Or your deployed URL
fetch(`${baseUrl}/${username}/stats`)
	.then((response) => response.json())
	.then((data) => console.log(data));
```

## Installation

### Setup

1. Clone the repository

   ```bash
   git clone https://github.com/tashifkhan/GitHub-Stats-API.git
   cd GitHub-Stats-API
   ```

2. Create and activate a virtual environment

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

4. Configure a .env file with your GitHub token

   ```env
   GITHUB_TOKEN=your_personal_access_token
   PORT=8000 # Optional: Uvicorn default is 8000
   ```

5. Start the FastAPI application using Uvicorn
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   Or simply run the `app.py` script if you prefer the `if __name__ == "__main__":` block:
   ```bash
   python app.py
   ```

The API will be available at `http://localhost:8000`.
The custom documentation page will be at `http://localhost:8000/`.
Swagger UI docs at `http://localhost:8000/docs`.
ReDoc docs at `http://localhost:8000/redoc`.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](./LICENSE) for details.
