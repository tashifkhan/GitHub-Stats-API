# GitHub Stats API

A robust RESTful API built with FastAPI that retrieves and analyzes GitHub user data, including programming language statistics, contribution history, and profile views tracking.

hosted at ![github-stats.tashif.codes](https://github-stats.tashif.codes)

## Features

- Fetch programming language statistics used by any GitHub user
- Retrieve detailed contribution history and metrics
- View total commits and longest streak information
- Get comprehensive user statistics in a single request
- Track profile visitors count (similar to GitHub Profile Views Counter)
- Get detailed repository information including README content
- Retrieve commit history across all repositories
- Interactive API documentation (Swagger UI & ReDoc)
- Custom HTML documentation page
- Easy integration with other applications

### Get Complete Statistics

```
GET /{username}/stats
```

Get comprehensive GitHub statistics for a user, combining top programming languages, total contribution count, longest contribution streak, and profile visitors count.

#### Parameters

- `username` (path): GitHub username
- `exclude` (query, optional): Comma-separated list of languages to exclude

#### Response

Returns comprehensive data including top programming languages, total commits, longest streak, current streak, profile visitors, and contribution history.

#### Example Response

```json
{
	"status": "success",
	"message": "retrieved",
	"topLanguages": [{ "name": "Python", "percentage": 45.0 }],
	"totalCommits": 1234,
	"longestStreak": 30,
	"currentStreak": 15,
	"profile_visitors": 567,
	"contributions": { ... }
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
		}
	},
	"totalCommits": 1234,
	"longestStreak": 30
}
```

### Get Repository Details

```
GET /{username}/repos
```

Retrieves detailed information for each of the user's public repositories, including README content, languages, and commit count.

#### Parameters

- `username` (path): GitHub username

#### Response

Returns a list of repository details with comprehensive information.

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

Retrieves a list of all commits made by the user across their owned repositories, sorted by timestamp (most recent first).

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

### Get Profile Views

```
GET /{username}/profile-views
```

Gets the current profile views count for a user and optionally increments it. Similar to the GitHub Profile Views Counter service.

#### Parameters

- `username` (path): GitHub username
- `increment` (query, optional): Whether to increment the view count (default: true)
- `base` (query, optional): Base count to set (for migration from other services)

#### Response

Returns the profile views count and whether it was incremented.

#### Example Response

```json
{
	"username": "tashifkhan",
	"views": 1234,
	"incremented": true
}
```

#### Usage Examples

**Basic usage (increments count):**

```
GET /tashifkhan/profile-views
```

**Get count without incrementing:**

```
GET /tashifkhan/profile-views?increment=false
```

**Set base count for migration:**

```
GET /tashifkhan/profile-views?base=1000
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
	"currentStreak": 0,
	"profile_visitors": 0,
	"contributions": null
}
```

## Usage Examples

### Python

```python
import requests

username = "octocat"
# Update base URL if running locally, e.g., http://localhost:8000
base_url = "https://github-stats.tashif.codes" # Or your deployed URL

# Get complete statistics
response = requests.get(f"{base_url}/{username}/stats")
data = response.json()

print(f"{username} has made {data['totalCommits']} commits with a longest streak of {data['longestStreak']} days!")
print(f"Profile has been viewed {data['profile_visitors']} times!")

# Get repository details
repos_response = requests.get(f"{base_url}/{username}/repos")
repos = repos_response.json()

for repo in repos:
    print(f"Repository: {repo['title']}")
    print(f"Languages: {', '.join(repo['languages'])}")
    print(f"Commits: {repo['num_commits']}")

# Increment profile views
views_response = requests.get(f"{base_url}/{username}/profile-views")
views_data = views_response.json()
print(f"Profile views: {views_data['views']}")
```

### JavaScript

```javascript
const username = "octocat";
// Update base URL if running locally, e.g., http://localhost:8000
const baseUrl = "https://github-stats.tashif.codes"; // Or your deployed URL

// Get complete statistics
fetch(`${baseUrl}/${username}/stats`)
	.then((response) => response.json())
	.then((data) => {
		console.log(`Total commits: ${data.totalCommits}`);
		console.log(`Profile visitors: ${data.profile_visitors}`);
	});

// Get repository details
fetch(`${baseUrl}/${username}/repos`)
	.then((response) => response.json())
	.then((repos) => {
		repos.forEach((repo) => {
			console.log(`Repository: ${repo.title}`);
			console.log(`Languages: ${repo.languages.join(", ")}`);
		});
	});

// Increment profile views
fetch(`${baseUrl}/${username}/profile-views`)
	.then((response) => response.json())
	.then((data) => {
		console.log(`Profile views: ${data.views}`);
	});
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
