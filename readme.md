# GitHub Stats API

A robust RESTful API built with FastAPI that retrieves and analyzes GitHub user data, including programming language statistics and contribution history.

hosted at ![github-stats.tashif.codes](htpps://github-stats.tashif.codes)

## Features

- Fetch programming language statistics used by any GitHub user
- Retrieve detailed contribution history and metrics
- View total commits and longest streak information
- Get comprehensive user statistics in a single request
- Interactive API documentation
- Easy integration with other applications

## API Endpoints

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
	"topLanguages": [{ "name": "Python", "percentage": 45 }],
	"totalCommits": 1234,
	"longestStreak": 30,
	"status": "success",
	"message": "retrieved",
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
	}
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
{
	"topLanguages": [{ "name": "Python", "percentage": 45 }],
	"status": "success",
	"message": "retrieved"
}
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
	"longestStreak": 30,
	"status": "success",
	"message": "retrieved"
}
```

## API Documentation

API documentation is available when the server is running `/`

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
	"longestStreak": 0
}
```

## Usage Examples

### Python

```python
import requests

username = "octocat"
response = requests.get(f"http://localhost:8000/{username}/stats")
data = response.json()

print(f"{username} has made {data['totalCommits']} commits with a longest streak of {data['longestStreak']} days!")
```

### JavaScript

```javascript
fetch(`http://localhost:8000/${username}/stats`)
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

   ```
   GITHUB_TOKEN=your_personal_access_token
   ```

5. Start the Flask application
   ```bash
   python app.py
   ```

The API will be available at `http://localhost:8909`.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](./LICENSE) for details.
