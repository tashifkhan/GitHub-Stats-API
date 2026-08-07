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

- **`exclude`** (query, optional): Comma-separated list of languages to exclude (preferred).
- **`excluded`** (query, optional, legacy): Repeatable query param for backwards compatibility, e.g. `?excluded=HTML&excluded=CSS`.

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

- **`exclude`** (query, optional): Comma-separated list of languages to exclude (preferred).
- **`excluded`** (query, optional, legacy): Repeatable query param for backwards compatibility.
- **`attributed`** (query, optional, default `true`): Count only lines the user wrote. See [Own-commit attribution](#own-commit-attribution).
- **`include_forks`** (query, optional, default `true`): Include forks, counting only the user's commits in them.

### Get Own-Commit Contribution Breakdown

`GET /{username}/contributions/breakdown`

Per-repository view of what the user personally wrote: commits, additions,
deletions, files touched, language mix, and their share of each repo's total
additions. Also reports `coverage` and `partial` (see below).

- **`exclude`** / **`excluded`** (query, optional): Languages to omit.
- **`include_forks`** (query, optional, default `true`).

### Get Contribution History

`GET /{username}/contributions`

- **`starting_year`** (query, optional): Starting year for the contribution history.

### Get Repository Details

`GET /{username}/repos`

Returns repository-level data including:

- Decoded README content as Markdown (`readme`)
- GitHub topics / tags (`topics`)
- Latest releases (`releases`)
- Release notes/body in Markdown (`releases[].body`)
- Release asset download links (`releases[].assets[].download_url`)

Example:

```json
[
  {
    "title": "RepoName",
    "languages": ["Python", "JavaScript"],
    "topics": ["fastapi", "api", "dashboard"],
    "readme": "# RepoName\n\nProject documentation in markdown.",
    "releases": [
      {
        "tag_name": "v1.2.0",
        "body": "## Changelog\n\n- Added release support",
        "url": "https://github.com/user/RepoName/releases/tag/v1.2.0",
        "assets": [
          {
            "name": "RepoName-v1.2.0.zip",
            "download_url": "https://github.com/user/RepoName/releases/download/v1.2.0/RepoName-v1.2.0.zip"
          }
        ]
      }
    ]
  }
]
```

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

## Own-commit attribution

Language percentages and the per-repo `user_*` fields describe only the commits
the requested user authored. A fork counts the patches they wrote rather than
the upstream codebase, and in their own repos other contributors' commits are
ignored. Vendored paths (`node_modules`, `dist`, lockfiles, generated and
minified files) are skipped so they cannot dominate the split.

This is measured by walking commit diffs, which costs hundreds of GitHub API
calls and takes minutes for a large account — far longer than a single request
may run. So:

- Every walk is bounded by a wall-clock deadline and caches each repo it
  measures, keyed by that repo's `pushed_at`. Repos are only re-measured after
  they receive new commits.
- Until enough repos are cached to be representative (`ATTRIBUTION_MIN_COVERAGE`,
  default 70%), `/{username}/languages` and `/{username}/stats` serve the
  whole-repo language byte split instead. Responses say which is which via
  `coverage` and `partial` on the breakdown endpoint.
- `/{username}/repos` reads the attribution cache but never walks diffs itself,
  because it is already the heaviest endpoint in the API.

**A cache is required.** Without one nothing accumulates between requests and
the attributed split never reaches its coverage threshold, so the API quietly
serves whole-repo bytes forever. Configure either:

- `REDIS_URL` — a `redis://` / `rediss://` URL, used in preference when set; or
- `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` — what Vercel's Upstash
  integration provisions. These are used over Upstash's REST API, which also
  suits serverless better than a pooled TCP connection.

`/{username}/contributions/breakdown` reports `cache_enabled`, plus a `status`
and `message` saying why a walk stopped (`complete`, `deadline`, `rate_limited`,
`cache_disabled`) — check those first when the attributed split does not appear.

To compute attribution up front rather than waiting for it to trickle in:

```bash
python scripts/warm_attribution.py tashifkhan
```

If the deployment's cache credentials are not readable locally, warm it through
the API instead — each call measures more and caches it:

```bash
for i in $(seq 6); do curl -s https://your-api/tashifkhan/contributions/breakdown \
  | python -c 'import json,sys; d=json.load(sys.stdin); print(d["coverage"], d["status"])'; done
```

Tuning knobs (all optional, with defaults): `ATTRIBUTION_INLINE_DEADLINE` (3.5s
budget inside a request), `ATTRIBUTION_BREAKDOWN_DEADLINE` (45s),
`ATTRIBUTION_MIN_COVERAGE` (0.7), `ATTRIBUTION_MAX_REPOS` (60),
`ATTRIBUTION_MAX_COMMITS_PER_REPO` (200), `ATTRIBUTION_MAX_COMMIT_DETAILS` (600),
`ATTRIBUTION_RATE_LIMIT_FLOOR` (500 calls kept in reserve for other endpoints),
`ATTRIBUTION_CACHE_TTL_SECONDS` (7 days).

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
