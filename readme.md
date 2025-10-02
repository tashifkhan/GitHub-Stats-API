# GitHub Analytics API & Dashboard

A FastAPI-driven API and interactive dashboard for in-depth analysis of GitHub user statistics. This tool goes beyond simple data retrieval, offering a rich, interactive experience for exploring user data, including an innovative "GitHub Profile Stalker" for a comprehensive look at any user's profile.

**Live at: [github-stats.tashif.codes](https://github-stats.tashif.codes)**

## Features

- **Interactive GitHub Profile Stalker**: A user-friendly dashboard to search for any GitHub user and get a complete overview of their stats.
- **Comprehensive Statistics**: Fetch detailed data including programming language usage, contribution history, commit streaks, and total stars.
- **Data Visualizations**: Includes a beautiful line chart for contribution history and a breakdown of language usage.
- **Profile Views Tracking**: A simple endpoint to track and display profile views, similar to the popular GitHub Profile Views Counter.
- **Detailed Repository Information**: Get information on all of a user's public repositories, including READMEs, commit counts, and more.
- **RESTful API**: A well-documented API with interactive documentation (Swagger UI & ReDoc) for easy integration.

## Interactive Dashboard

The heart of this project is the interactive dashboard, which you can access at the root URL (`/`). It includes the following features:

- **GitHub Profile Stalker**: Simply enter a GitHub username to get a full breakdown of their profile.
- **Profile Overview**: Key metrics like total commits, longest streak, current streak, and total stars at a glance.
- **Top Languages**: A chart showing the user's most used programming languages.
- **Contribution Chart**: A line chart showing contribution activity over the last year.
- **Repository Details**: See top repositories, recent commits, and a list of all repositories.

## API Endpoints

### Get Complete Statistics

`GET /{username}/stats`

Fetches comprehensive statistics for a user, including language stats, contribution history, and profile views.

- **`exclude`** (query, optional): Comma-separated list of languages to exclude.

**Example Response:**

```json
{
    "status": "success",
    "message": "retrieved",
    "topLanguages": [{"name": "Python", "percentage": 45.0}],
    "totalCommits": 2068,
    "longestStreak": 25,
    "currentStreak": 10,
    "profile_visitors": 1234,
    "contributions": { ... }
}
```

### Get Language Statistics

`GET /{username}/languages`

- **`exclude`** (query, optional): Comma-separated list of languages to exclude.

### Get Contribution History

`GET /{username}/contributions`

- **`starting_year`** (query, optional): Starting year for the contribution history.

### Get Repository Details

`GET /{username}/repos`

### Get Stars Information

`GET /{username}/stars`

### Get Starred Lists

`GET /{username}/star-lists`

Optional: `?include_repos=true` to also include the repositories inside each curated list.

Example:

```json
[
	{
		"name": "AI Projects",
		"url": "https://github.com/stars/username/lists/ai-projects",
		"repositories": ["pytorch/pytorch", "huggingface/transformers"]
	}
]
```

### Get Commit History

`GET /{username}/commits`

### Get Profile Views

`GET /{username}/profile-views`

- **`increment`** (query, optional): `true` or `false`
- **`base`** (query, optional): A number to set as the base count.

## Local Development

To run this project locally, follow these steps:

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/tashifkhan/GitHub-Stats-API.git
    cd GitHub-Stats-API
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Create a `.env` file** and add your GitHub token:

    ```
    GITHUB_TOKEN=your_github_token_here
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

The application will be available at `http://localhost:8989`.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](./LICENSE) for details.
