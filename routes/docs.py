from fastapi import APIRouter
from fastapi.responses import HTMLResponse

docs_router = APIRouter()

docs_html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GitHub Stats API Documentation</title>
            <style>
                :root {
                    --primary-color: #e4e4e4;
                    --secondary-color: #64ffda;
                    --background-color: #0a192f;
                    --code-background: #112240;
                    --text-color: #8892b0;
                    --heading-color: #ccd6f6;
                    --card-background: #112240;
                    --hover-color: #233554;
                }
                body {
                    font-family: 'SF Mono', 'Fira Code', 'Monaco', monospace;
                    line-height: 1.6;
                    color: var(--text-color);
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 4rem 2rem;
                    background: var(--background-color);
                    transition: all 0.25s ease-in-out;
                }
                h1, h2, h3 {
                    color: var(--heading-color);
                    padding-bottom: 0.75rem;
                    margin-top: 2rem;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }
                h1 {
                    font-size: clamp(1.8rem, 4vw, 2.5rem);
                    margin-bottom: 2rem;
                    border-bottom: 2px solid var(--secondary-color);
                }
                
                /* API Section Styles */
                .api-section {
                    border-radius: 12px;
                    margin: 2.5rem 0;
                    box-shadow: 0 10px 30px -15px rgba(2,12,27,0.7);
                    border: 1px solid var(--hover-color);
                    overflow: hidden;
                    background: var(--card-background);
                }
                .section-header {
                    padding: 1.5rem;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    transition: background-color 0.2s ease;
                }
                .section-header:hover {
                    background-color: var(--hover-color);
                }
                .section-header h2 {
                    margin: 0;
                    padding: 0;
                    border: none;
                    font-size: 1.6rem; 
                    color: var(--heading-color);
                }
                .section-content {
                    max-height: 0;
                    overflow: hidden;
                    transition: max-height 0.35s ease-out;
                    padding: 0 1.5rem;
                }
                .api-section.active .section-content {
                    max-height: 10000px; /* Large enough for all content */
                    padding: 0.5rem 1.5rem 1.5rem;
                }
                .section-toggle {
                    font-size: 1.8rem;
                    font-weight: bold;
                    color: var(--secondary-color);
                    transition: transform 0.3s ease;
                }
                .api-section.active .section-toggle {
                    transform: rotate(180deg);
                }
                
                .endpoint {
                    background: #172a45;
                    border-radius: 12px;
                    padding: 0;
                    margin: 1.5rem 0;
                    box-shadow: 0 10px 30px -15px rgba(2,12,27,0.7);
                    border: 1px solid var(--hover-color);
                    transition: all 0.2s ease-in-out;
                    overflow: hidden;
                }
                .endpoint-header {
                    padding: 1.5rem;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    transition: background-color 0.2s ease;
                }
                .endpoint-header:hover {
                    background-color: var(--hover-color);
                }
                .endpoint-header h2 {
                    margin: 0;
                    padding: 0;
                    border: none;
                    font-size: 1.1rem;
                    display: flex;
                    align-items: center;
                }
                .endpoint-header h2 .path {
                    margin-left: 0.5rem;
                    margin-right: 0.5rem;
                    font-weight: 600;
                }
                .endpoint-content {
                    max-height: 0;
                    overflow: hidden;
                    transition: max-height 0.3s ease;
                    padding: 0 1.5rem;
                }
                .endpoint.active .endpoint-content {
                    max-height: 5000px; /* Large enough to show all content */
                    padding: 0 1.5rem 1.5rem;
                }
                .endpoint-toggle {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: var(--secondary-color);
                    transition: transform 0.3s ease;
                }
                .endpoint.active .endpoint-toggle {
                    transform: rotate(45deg);
                }
                code {
                    background: var(--code-background);
                    color: var(--secondary-color);
                    padding: 0.3rem 0.6rem;
                    border-radius: 6px;
                    font-family: 'SF Mono', 'Fira Code', monospace;
                    font-size: 0.85em;
                    word-break: break-word;
                    white-space: pre-wrap;
                }
                pre {
                    background: var(--code-background);
                    padding: 1.5rem;
                    border-radius: 12px;
                    overflow-x: auto;
                    margin: 1.5rem 0;
                    border: 1px solid var(--hover-color);
                    position: relative;
                }
                pre code {
                    padding: 0;
                    background: none;
                    color: var(--primary-color);
                    font-size: 0.9em;
                }
                .parameter {
                    margin: 1.5rem 0;
                    padding: 1.25rem;
                    background: var(--hover-color);
                    border-radius: 8px;
                    box-shadow: 0 4px 12px -6px rgba(2,12,27,0.4);
                    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                }
                .parameter:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 16px -6px rgba(2,12,27,0.5);
                }
                .parameter code {
                    font-size: 0.95em;
                    font-weight: 500;
                    margin-right: 0.5rem;
                }
                .error-response {
                    padding: 1.25rem;
                    margin: 1.25rem 0;
                    background: var(--hover-color);
                    border-radius: 8px;
                    overflow-x: auto;
                }
                .note {
                    background: var(--hover-color);
                    padding: 1.25rem;
                    margin: 1.25rem 0;
                    border-radius: 8px;
                }
                @media (max-width: 768px) {
                    body {
                        padding: 1rem 0.75rem;
                    }
                    .section-header {
                        padding: 1.25rem;
                    }
                    .section-header h2 {
                        font-size: 1.4rem;
                    }
                    .endpoint-header {
                        padding: 1.25rem;
                    }
                    .endpoint-header h2 {
                        font-size: 1rem;
                        flex-direction: column;
                        align-items: flex-start;
                    }
                    .endpoint-header h2 .path {
                        margin-left: 0;
                        margin-top: 0.25rem;
                        margin-bottom: 0.25rem;
                    }
                    pre {
                        padding: 1rem;
                        font-size: 0.9em;
                    }
                    code {
                        font-size: 0.8em;
                    }
                }
                @media (max-width: 480px) {
                    body {
                        padding: 1rem 0.5rem;
                    }
                    .section-header {
                        padding: 1rem;
                    }
                    .section-header h2 {
                        font-size: 1.3rem;
                    }
                    .endpoint-header {
                        padding: 1rem;
                    }
                    .endpoint-header h2 {
                        font-size: 0.9rem;
                    }
                    h1 {
                        font-size: 1.8rem;
                    }
                    pre {
                        padding: 0.75rem;
                        font-size: 0.85em;
                    }
                    .parameter, .error-response, .note {
                        padding: 1rem;
                        margin: 1rem 0;
                    }
                }
                .method {
                    color: #ff79c6;
                    font-weight: bold;
                }
                .path {
                    color: var(--secondary-color);
                }
                .endpoint-method {
                    display: inline-block;
                    padding: 0.3rem 0.5rem;
                    background: #ff79c6;
                    color: var(--background-color);
                    border-radius: 4px;
                    font-weight: bold;
                    margin-right: 0.5rem;
                }
                ::selection {
                    background: var(--secondary-color);
                    color: var(--background-color);
                }
                .error-section {
                    margin: 2rem 0;
                }
                .error-section h2 {
                    border-bottom: 2px solid var(--secondary-color);
                    padding-bottom: 0.75rem;
                }
                .error-item {
                    margin-bottom: 1rem;
                }
                .error-toggle {
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem;
                    background: var(--card-background);
                    border-radius: 8px;
                    margin-bottom: 1rem;
                    border: 1px solid var(--hover-color);
                }
                .error-toggle:hover {
                    background: var(--hover-color);
                }
                .error-toggle h3 {
                    margin: 0;
                    padding: 0;
                    border: none;
                }
                .error-content {
                    max-height: 0;
                    overflow: hidden;
                    transition: max-height 0.3s ease;
                }
                .error-item.active .error-content {
                    max-height: 1000px;
                }
                .error-toggle-icon {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: var(--secondary-color);
                    transition: transform 0.3s ease;
                }
                .error-item.active .error-toggle-icon {
                    transform: rotate(45deg);
                }
                footer {
                    margin-top: 3rem;
                    padding-top: 1.5rem;
                    border-top: 1px solid var(--hover-color);
                    text-align: center;
                    color: var(--text-color);
                    font-size: 0.9em;
                }
            </style>
        </head>
        <body>
            <h1>GitHub Stats API Documentation</h1>
            
            <p>This API provides access to GitHub user statistics and contribution data. Click on each endpoint to see details.</p>
            <p>
                Interactive API documentation (Swagger UI) is available at <a href="/docs" style="color: var(--secondary-color);">/docs</a>.
                Alternative API documentation (ReDoc) is available at <a href="/redoc" style="color: var(--secondary-color);">/redoc</a>.
            </p>

            <!-- General Section -->
            <div class="api-section">
                <div class="section-header">
                    <h2>General</h2>
                    <span class="section-toggle">&#9660;</span>
                </div>
                <div class="section-content">
                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/</code> Custom API Documentation</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Provides this custom HTML documentation page for the API.</p>
                            <p>For interactive API exploration and testing, you can use:
                                <ul>
                                    <li>Swagger UI: <a href="/docs" style="color: var(--secondary-color);">/docs</a></li>
                                    <li>ReDoc: <a href="/redoc" style="color: var(--secondary-color);">/redoc</a></li>
                                </ul>
                            </p>
                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /</code></pre>
                            </div>
                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-html">&lt;!DOCTYPE html&gt;
&lt;html&gt;
    &lt;head&gt;...&lt;/head&gt;
    &lt;body&gt;... API Documentation ...&lt;/body&gt;
&lt;/html&gt;</code></pre>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/docs</code> Swagger UI API Documentation</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Provides interactive API documentation using Swagger UI. This interface allows you to explore endpoints, view models, and test API calls directly in your browser.</p>
                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /docs</code></pre>
                            </div>
                            <div class="response">
                                <h3>Response</h3>
                                <p>Returns the Swagger UI interface.</p>
                                <pre><code class="language-html">&lt;!DOCTYPE html&gt;
&lt;html&gt;
    &lt;head&gt;... Swagger UI ...&lt;/head&gt;
    &lt;body&gt;... Interactive Documentation ...&lt;/body&gt;
&lt;/html&gt;</code></pre>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/redoc</code> ReDoc API Documentation</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Provides alternative API documentation using ReDoc. This interface offers a clean, three-panel view of your API specification, ideal for reading and understanding the API structure.</p>
                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /redoc</code></pre>
                            </div>
                            <div class="response">
                                <h3>Response</h3>
                                <p>Returns the ReDoc UI interface.</p>
                                <pre><code class="language-html">&lt;!DOCTYPE html&gt;
&lt;html&gt;
    &lt;head&gt;... ReDoc ...&lt;/head&gt;
    &lt;body&gt;... API Documentation ...&lt;/body&gt;
&lt;/html&gt;</code></pre>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- User Analytics Section -->
            <div class="api-section">
                <div class="section-header">
                    <h2>User Analytics</h2>
                    <span class="section-toggle">&#9660;</span>
                </div>
                <div class="section-content">
                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/languages</code> Get User's Programming Languages</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Get the programming languages used in a GitHub user's repositories.</p>
                            
                            <h3>Parameters</h3>
                            <div class="parameter">
                                <code>exclude</code> Optional comma-separated list of languages to exclude (default: Markdown, JSON, YAML, XML)
                            </div>

                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/languages?exclude=HTML,CSS</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">[
    {
        "name": "Python", 
        "percentage": 45.0
    },
    {
        "name": "JavaScript", 
        "percentage": 30.0
    }
]</code></pre>
                            </div>

                            <div class="error-response">
                                <h3>Error Responses</h3>
                                <p><code>404</code> - User not found or API error</p>
                                <p><code>500</code> - GitHub token configuration error</p>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/contributions</code> Get User's Contribution History</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Retrieve a user's GitHub contribution history and statistics, including contribution calendar data, total commits, and longest streak.</p>
                            
                            <div class="parameter">
                                <code>starting_year</code> Optional starting year for contribution history (defaults to account creation year)
                            </div>

                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/contributions?starting_year=2022</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">{
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
    "currentStreak": 15
}</code></pre>
                            </div>

                            <div class="error-response">
                                <h3>Error Responses</h3>
                                <p><code>404</code> - User not found or API error</p>
                                <p><code>500</code> - GitHub token configuration error</p>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/stats</code> Get User's Complete Statistics</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Get comprehensive GitHub statistics for a user, combining top programming languages, total contribution count, longest contribution streak, current streak, profile visitors count, and contribution history data.</p>
                            
                            <div class="parameter">
                                <code>exclude</code> Optional comma-separated list of languages to exclude
                            </div>

                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/stats?exclude=HTML,CSS,Markdown</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">{
    "status": "success",
    "message": "retrieved",
    "topLanguages": [
        {"name": "Python", "percentage": 45}
    ],
    "totalCommits": 1234,
    "longestStreak": 30,
    "currentStreak": 15,
    "profile_visitors": 567,
    "contributions": { ... }
}</code></pre>
                            </div>

                            <div class="error-response">
                                <h3>Error Responses</h3>
                                <p><code>404</code> - User not found or API error</p>
                                <p><code>500</code> - GitHub token configuration error</p>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/profile-views</code> Get and Increment Profile Views</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Gets the current profile views count for a user and optionally increments it. Similar to the GitHub Profile Views Counter service.</p>
                            
                            <div class="parameter">
                                <code>increment</code> Optional boolean to increment the view count (default: true)
                            </div>
                            <div class="parameter">
                                <code>base</code> Optional base count to set (for migration from other services)
                            </div>

                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/profile-views?increment=true</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">{
    "username": "tashifkhan",
    "views": 1234,
    "incremented": true
}</code></pre>
                            </div>

                            <div class="note">
                                <h3>Usage Examples</h3>
                                <p><strong>Basic usage (increments count):</strong></p>
                                <pre><code>GET /tashifkhan/profile-views</code></pre>
                                
                                <p><strong>Get count without incrementing:</strong></p>
                                <pre><code>GET /tashifkhan/profile-views?increment=false</code></pre>
                                
                                <p><strong>Set base count for migration:</strong></p>
                                <pre><code>GET /tashifkhan/profile-views?base=1000</code></pre>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Dashboard Details Section -->
            <div class="api-section">
                <div class="section-header">
                    <h2>Dashboard Details</h2>
                    <span class="section-toggle">&#9660;</span>
                </div>
                <div class="section-content">
                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/repos</code> Get User's Repository Details</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Retrieves detailed information for each of the user's public repositories, including README content (Base64 encoded), languages, and commit count.</p>
                            
                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/repos</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">[
    {
        "title": "RepoName",
        "description": "A cool project.",
        "live_website_url": "https://example.com",
        "languages": ["Python", "JavaScript"],
        "num_commits": 42,
        "readme": "BASE64_ENCODED_README_CONTENT"
    }
]</code></pre>
                            </div>

                            <div class="error-response">
                                <h3>Error Responses</h3>
                                <p><code>404</code> - User not found (may return empty list if service handles this way)</p>
                                <p><code>500</code> - GitHub token configuration error or API error</p>
                            </div>
                        </div>
                    </div>

                    <div class="endpoint">
                        <div class="endpoint-header">
                            <h2><span class="endpoint-method">GET</span><code class="path">/{username}/commits</code> Get User's Commit History Across All Repositories</h2>
                            <span class="endpoint-toggle">+</span>
                        </div>
                        <div class="endpoint-content">
                            <p>Retrieves a list of all commits made by the user across all their owned repositories, sorted by timestamp (most recent first).</p>

                            <div class="note">
                                <h3>Example Request</h3>
                                <pre><code>GET /tashifkhan/commits</code></pre>
                            </div>

                            <div class="response">
                                <h3>Response</h3>
                                <pre><code class="language-json">[
    {
        "repo": "RepoName",
        "message": "Fix: A critical bug",
        "timestamp": "2023-01-01T12:00:00Z",
        "sha": "commit_sha_hash",
        "url": "https://github.com/user/repo/commit/sha"
    }
]</code></pre>
                            </div>

                            <div class="error-response">
                                <h3>Error Responses</h3>
                                <p><code>404</code> - User not found (may return empty list if service handles this way)</p>
                                <p><code>500</code> - GitHub token configuration error or API error</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="error-section">
                <h2>Error Responses</h2>
                
                <div class="error-item">
                    <div class="error-toggle">
                        <h3>User not found</h3>
                        <span class="error-toggle-icon">+</span>
                    </div>
                    <div class="error-content">
                        <pre><code>{
    "status": "error",
    "message": "User not found or API error",
    "topLanguages": [],
    "totalCommits": 0,
    "longestStreak": 0,
    "currentStreak": 0
}</code></pre>
                    </div>
                </div>

                <div class="error-item">
                    <div class="error-toggle">
                        <h3>Server error</h3>
                        <span class="error-toggle-icon">+</span>
                    </div>
                    <div class="error-content">
                        <pre><code>{
    "status": "error",
    "message": "GitHub token not configured",
    "topLanguages": [],
    "totalCommits": 0,
    "longestStreak": 0,
    "currentStreak": 0
}</code></pre>
                    </div>
                </div>
            </div>

            <footer>
                <p>GitHub Analytics API live at <a href="https://github-stats.tashif.codes" style="color: var(--secondary-color); text-decoration: none;">github-stats.tashif.codes</a></p>
                <p>This API is open source and available on <a href="https://github.com/tashifkhan/GitHub-Stats-API.git" style="color: var(--secondary-color); text-decoration: none;">GitHub</a></p>
            </footer>

            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // Handle endpoint toggles
                    const endpoints = document.querySelectorAll('.endpoint');
                    endpoints.forEach(endpoint => {
                        const header = endpoint.querySelector('.endpoint-header');
                        header.addEventListener('click', () => {
                            endpoint.classList.toggle('active');
                        });
                    });
                    
                    // Handle API section toggles
                    const apiSections = document.querySelectorAll('.api-section');
                    apiSections.forEach(section => {
                        const header = section.querySelector('.section-header');
                        header.addEventListener('click', () => {
                            section.classList.toggle('active');
                        });
                    });
                    
                    // Handle error toggles
                    const errorItems = document.querySelectorAll('.error-item');
                    errorItems.forEach(item => {
                        const toggle = item.querySelector('.error-toggle');
                        toggle.addEventListener('click', () => {
                            item.classList.toggle('active');
                        });
                    });
                    
                    // Make all API sections active by default
                    apiSections.forEach(section => {
                        section.classList.add('active');
                    });
                });
            </script>
        </body>
        </html>
    """


@docs_router.get("/", response_class=HTMLResponse, tags=["Documentation"])
async def get_custom_documentation():
    """
    Serves the custom HTML API documentation page.
    """
    return HTMLResponse(content=docs_html_content)
