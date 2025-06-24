from fastapi import APIRouter
from fastapi.responses import HTMLResponse

docs_router = APIRouter()

docs_html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GitHub Analytics Dashboard and API Documentation</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
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
                        padding: 2rem 1rem;
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
                    .stalker-form {
                        padding: 1.5rem;
                    }
                    .profile-section {
                        padding: 1.5rem;
                    }
                    #contribution-chart-container {
                        height: 30vh;
                    }
                    .input-group {
                        flex-direction: column;
                    }
                    
                    .input-container {
                        width: 100%;
                    }
                    
                    .clear-history-btn {
                        right: 0.75rem;
                    }
                    
                    .history-dropdown {
                        max-height: 250px;
                    }
                    
                    .history-list {
                        max-height: 200px;
                    }
                    
                    .profile-cards {
                        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    }
                    
                    .repos-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .contribution-graph {
                        grid-template-columns: repeat(26, 1fr);
                    }
                }
                @media (max-width: 480px) {
                    body {
                        padding: 1.5rem 0.75rem;
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
                        font-size: 1.6rem;
                    }
                    pre {
                        padding: 0.75rem;
                        font-size: 0.85em;
                    }
                    .parameter, .error-response, .note {
                        padding: 1rem;
                        margin: 1rem 0;
                    }
                    .stalker-form {
                        padding: 1rem;
                    }
                    .profile-section {
                        padding: 1rem;
                    }
                    .profile-card {
                        padding: 1rem;
                    }
                    .card-value {
                        font-size: 1.8rem;
                    }
                    .repo-card {
                        padding: 1rem;
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
                
                /* GitHub Profile Stalker Styles */
                .stalker-form {
                    background: var(--card-background);
                    border-radius: 12px;
                    padding: 2rem;
                    margin: 2rem 0;
                    border: 1px solid var(--hover-color);
                    text-align: center;
                }
                
                .stalker-form h3 {
                    margin-bottom: 1.5rem;
                    color: var(--heading-color);
                }
                
                .input-group {
                    display: flex;
                    gap: 1rem;
                    max-width: 500px;
                    margin: 0 auto;
                }
                
                .input-container {
                    position: relative;
                    flex: 1;
                    display: flex;
                    align-items: center;
                }
                
                .input-container input {
                    width: 100%;
                    padding: 0.75rem 2.5rem 0.75rem 1rem;
                    border: 2px solid var(--hover-color);
                    border-radius: 8px;
                    background: var(--code-background);
                    color: var(--text-color);
                    font-family: inherit;
                    font-size: 1rem;
                    transition: border-color 0.2s ease;
                }
                
                .input-container input:focus {
                    outline: none;
                    border-color: var(--secondary-color);
                }
                
                .clear-history-btn {
                    position: absolute;
                    right: 0.5rem;
                    background: none;
                    border: none;
                    color: var(--text-color);
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 4px;
                    transition: all 0.2s ease;
                    opacity: 0.7;
                }
                
                .clear-history-btn:hover {
                    opacity: 1;
                    color: var(--secondary-color);
                    background: var(--hover-color);
                }
                
                .clear-history-btn .icon {
                    width: 1rem;
                    height: 1rem;
                }
                
                .input-group input {
                    flex: 1;
                    padding: 0.75rem 1rem;
                    border: 2px solid var(--hover-color);
                    border-radius: 8px;
                    background: var(--code-background);
                    color: var(--text-color);
                    font-family: inherit;
                    font-size: 1rem;
                    transition: border-color 0.2s ease;
                }
                
                .input-group input:focus {
                    outline: none;
                    border-color: var(--secondary-color);
                }
                
                .stalk-button {
                    padding: 0.75rem 1.5rem;
                    background: var(--secondary-color);
                    color: var(--background-color);
                    border: none;
                    border-radius: 8px;
                    font-family: inherit;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .stalk-button:hover {
                    background: #4cd4b0;
                    transform: translateY(-2px);
                }
                
                .loading {
                    text-align: center;
                    margin: 2rem 0;
                }
                
                .spinner {
                    width: 40px;
                    height: 40px;
                    border: 4px solid var(--hover-color);
                    border-top: 4px solid var(--secondary-color);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 1rem;
                }
                
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                .profile-results {
                    margin-top: 2rem;
                }
                
                .profile-section {
                    background: var(--card-background);
                    border-radius: 12px;
                    padding: 2rem;
                    margin: 2rem 0;
                    border: 1px solid var(--hover-color);
                }
                
                .profile-section h3 {
                    margin-bottom: 1.5rem;
                    color: var(--heading-color);
                    border-bottom: 2px solid var(--secondary-color);
                    padding-bottom: 0.5rem;
                }
                
                .profile-cards {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 1.5rem;
                }
                
                .profile-card {
                    background: var(--hover-color);
                    border-radius: 12px;
                    padding: 1.5rem;
                    text-align: center;
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                }
                
                .profile-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 8px 25px rgba(2,12,27,0.3);
                }
                
                .card-icon {
                    font-size: 2rem;
                    margin-bottom: 1rem;
                }
                
                .icon {
                    width: 1em;
                    height: 1em;
                    vertical-align: middle;
                    margin-right: 0.5rem;
                }
                
                .card-icon .icon {
                    width: 2rem;
                    height: 2rem;
                    margin-right: 0;
                    color: var(--secondary-color);
                }
                
                .profile-section h3 .icon {
                    width: 1.2rem;
                    height: 1.2rem;
                    margin-right: 0.5rem;
                    color: var(--secondary-color);
                }
                
                .stalk-button .icon {
                    width: 1rem;
                    height: 1rem;
                    margin-right: 0.5rem;
                }
                
                .card-content h4 {
                    color: var(--text-color);
                    margin-bottom: 0.5rem;
                    font-size: 0.9rem;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                
                .card-value {
                    color: var(--secondary-color);
                    font-size: 2rem;
                    font-weight: 700;
                }
                
                .languages-chart {
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                }
                
                .language-bar {
                    background: var(--hover-color);
                    border-radius: 8px;
                    padding: 1rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .language-info {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }
                
                .language-color {
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    border: 2px solid var(--text-color);
                }
                
                .language-name {
                    font-weight: 600;
                    color: var(--heading-color);
                }
                
                .language-percentage {
                    color: var(--secondary-color);
                    font-weight: 600;
                }
                
                .contribution-graph {
                    display: grid;
                    grid-template-columns: repeat(53, 1fr);
                    gap: 2px;
                    max-width: 100%;
                    overflow-x: auto;
                    padding: 1rem 0;
                }
                
                .contribution-day {
                    width: 12px;
                    height: 12px;
                    border-radius: 2px;
                    background: var(--hover-color);
                    transition: transform 0.2s ease;
                }
                
                .contribution-day:hover {
                    transform: scale(1.5);
                }
                
                .contribution-day[data-level="0"] { background: #ebedf0; }
                .contribution-day[data-level="1"] { background: #9be9a8; }
                .contribution-day[data-level="2"] { background: #40c463; }
                .contribution-day[data-level="3"] { background: #30a14e; }
                .contribution-day[data-level="4"] { background: #216e39; }
                
                .repos-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 1.5rem;
                }
                
                .repo-card {
                    background: var(--hover-color);
                    border-radius: 12px;
                    padding: 1.5rem;
                    border: 1px solid var(--card-background);
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                }
                
                .repo-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 8px 25px rgba(2,12,27,0.3);
                }
                
                .repo-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 1rem;
                }
                
                .repo-name {
                    color: var(--secondary-color);
                    font-weight: 600;
                    font-size: 1.1rem;
                    text-decoration: none;
                }
                
                .repo-name:hover {
                    text-decoration: underline;
                }
                
                .repo-stars {
                    background: var(--secondary-color);
                    color: var(--background-color);
                    padding: 0.25rem 0.5rem;
                    border-radius: 4px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }
                
                .repo-description {
                    color: var(--text-color);
                    margin-bottom: 1rem;
                    line-height: 1.5;
                }
                
                .repo-meta {
                    display: flex;
                    gap: 1rem;
                    font-size: 0.9rem;
                    color: var(--text-color);
                }
                
                .repo-language {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                
                .repo-language-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: var(--secondary-color);
                }
                
                .commits-list {
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                }
                
                .commit-item {
                    background: var(--hover-color);
                    border-radius: 8px;
                    padding: 1rem;
                    border-left: 4px solid var(--secondary-color);
                }
                
                .commit-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 0.5rem;
                }
                
                .commit-repo {
                    color: var(--secondary-color);
                    font-weight: 600;
                    font-size: 0.9rem;
                }
                
                .commit-date {
                    color: var(--text-color);
                    font-size: 0.8rem;
                }
                
                .commit-message {
                    color: var(--heading-color);
                    line-height: 1.4;
                }
                
                .error-message {
                    background: #ff6b6b;
                    color: white;
                    padding: 1rem;
                    border-radius: 8px;
                    text-align: center;
                    margin: 1rem 0;
                }
                
                @media (max-width: 768px) {
                    .input-group {
                        flex-direction: column;
                    }
                    
                    .profile-cards {
                        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    }
                    
                    .repos-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .contribution-graph {
                        grid-template-columns: repeat(26, 1fr);
                    }
                }
                
                /* Custom Dropdown Styles */
                .history-dropdown {
                    position: absolute;
                    top: 100%;
                    left: 0;
                    right: 0;
                    background: var(--card-background);
                    border: 1px solid var(--hover-color);
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                    box-shadow: 0 8px 25px rgba(2,12,27,0.3);
                    z-index: 1000;
                    opacity: 0;
                    visibility: hidden;
                    transform: translateY(-10px);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    max-height: 300px;
                    overflow: hidden;
                }
                
                .history-dropdown.active {
                    opacity: 1;
                    visibility: visible;
                    transform: translateY(0);
                }
                
                .dropdown-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 0.75rem 1rem;
                    border-bottom: 1px solid var(--hover-color);
                    background: var(--hover-color);
                }
                
                .dropdown-header span {
                    color: var(--heading-color);
                    font-size: 0.9rem;
                    font-weight: 600;
                }
                
                .clear-all-btn {
                    background: none;
                    border: none;
                    color: var(--text-color);
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 4px;
                    transition: all 0.2s ease;
                    opacity: 0.7;
                }
                
                .clear-all-btn:hover {
                    opacity: 1;
                    color: var(--secondary-color);
                    background: var(--card-background);
                }
                
                .clear-all-btn .icon {
                    width: 1rem;
                    height: 1rem;
                }
                
                .history-list {
                    max-height: 250px;
                    overflow-y: auto;
                }
                
                .history-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 0.75rem 1rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    border-bottom: 1px solid rgba(136, 146, 176, 0.1);
                }
                
                .history-item:last-child {
                    border-bottom: none;
                }
                
                .history-item:hover {
                    background: var(--hover-color);
                }
                
                .history-item.selected {
                    background: var(--secondary-color);
                    color: var(--background-color);
                }
                
                .history-username {
                    color: var(--text-color);
                    font-weight: 500;
                    flex: 1;
                }
                
                .history-item:hover .history-username,
                .history-item.selected .history-username {
                    color: inherit;
                }
                
                .history-delete-btn {
                    background: none;
                    border: none;
                    color: var(--text-color);
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 4px;
                    transition: all 0.2s ease;
                    opacity: 0;
                    margin-left: 0.5rem;
                }
                
                .history-item:hover .history-delete-btn {
                    opacity: 0.7;
                }
                
                .history-delete-btn:hover {
                    opacity: 1 !important;
                    color: #ff6b6b;
                    background: rgba(255, 107, 107, 0.1);
                }
                
                .history-delete-btn .icon {
                    width: 0.8rem;
                    height: 0.8rem;
                }
                
                .history-empty {
                    padding: 1rem;
                    text-align: center;
                    color: var(--text-color);
                    font-style: italic;
                    opacity: 0.7;
                }
                
                /* Scrollbar styling for dropdown */
                .history-list::-webkit-scrollbar {
                    width: 6px;
                }
                
                .history-list::-webkit-scrollbar-track {
                    background: var(--code-background);
                }
                
                .history-list::-webkit-scrollbar-thumb {
                    background: var(--hover-color);
                    border-radius: 3px;
                }
                
                .history-list::-webkit-scrollbar-thumb:hover {
                    background: var(--secondary-color);
                }
                
                .input-group input {
                    flex: 1;
                    padding: 0.75rem 1rem;
                    border: 2px solid var(--hover-color);
                    border-radius: 8px;
                    background: var(--code-background);
                    color: var(--text-color);
                    font-family: inherit;
                    font-size: 1rem;
                    transition: border-color 0.2s ease;
                }
                
                .input-group input:focus {
                    outline: none;
                    border-color: var(--secondary-color);
                }
            </style>
        </head>
        <body>
            <h1>GitHub Analytics Dashboard</h1>
            
            <p>An interactive dashboard for in-depth analysis of GitHub user statistics. Use the dashboard below to get a comprehensive look at any user's profile, including contribution history, language stats, and repository details.</p>

            <!-- Interactive Dashboard -->
            <div class="stalker-form">
                <h3>Explore a GitHub Profile</h3>
                <div class="input-group">
                    <div class="input-container">
                        <input type="text" id="github-username" placeholder="Enter GitHub username (e.g., tashifkhan)" autocomplete="off" />
                        <button type="button" id="clear-history" class="clear-history-btn" title="Clear search history">
                            <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                            </svg>
                        </button>
                        <div id="history-dropdown" class="history-dropdown">
                            <div class="dropdown-header">
                                <span>Recent Searches</span>
                                <button type="button" id="clear-all-history" class="clear-all-btn" title="Clear all history">
                                    <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M19 13H5v-2h14v2z"/>
                                    </svg>
                                </button>
                            </div>
                            <div id="history-list" class="history-list"></div>
                        </div>
                    </div>
                    <button onclick="stalkGitHubUser()" class="stalk-button">
                        <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                        Analyze Profile
                    </button>
                </div>
                <div id="loading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>Fetching GitHub data...</p>
                </div>
            </div>

            <div id="profile-results" class="profile-results" style="display: none;">
                <!-- Profile Overview -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg> Profile Overview</h3>
                    <div class="profile-cards">
                        <div class="profile-card">
                            <div class="card-icon">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
                            </div>
                            <div class="card-content">
                                <h4>Total Commits</h4>
                                <div id="total-commits" class="card-value">-</div>
                            </div>
                        </div>
                        <div class="profile-card">
                            <div class="card-icon">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                            </div>
                            <div class="card-content">
                                <h4>Longest Streak</h4>
                                <div id="longest-streak" class="card-value">-</div>
                            </div>
                        </div>
                        <div class="profile-card">
                            <div class="card-icon">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2.05v3.03c3.39.49 6 3.39 6 6.92 0 .9-.18 1.75-.5 2.54l2.6 1.53c.56-1.24.9-2.62.9-4.07 0-5.18-3.95-9.45-9-9.95zM12 19c-3.87 0-7-3.13-7-7 0-3.53 2.61-6.43 6-6.92V2.05c-5.05.5-9 4.76-9 9.95 0 5.52 4.47 10 9.99 10 3.31 0 6.24-1.61 8.06-4.09l-2.6-1.53C16.17 17.98 14.21 19 12 19z"/></svg>
                            </div>
                            <div class="card-content">
                                <h4>Current Streak</h4>
                                <div id="current-streak" class="card-value">-</div>
                            </div>
                        </div>
                        <div class="profile-card">
                            <div class="card-icon">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                            </div>
                            <div class="card-content">
                                <h4>Total Stars</h4>
                                <div id="total-stars" class="card-value">-</div>
                            </div>
                        </div>
                        <div class="profile-card">
                            <div class="card-icon">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                            </div>
                            <div class="card-content">
                                <h4>Repositories</h4>
                                <div id="total-repos" class="card-value">-</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Top Languages -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/></svg> Top Programming Languages</h3>
                    <div id="languages-chart" class="languages-chart"></div>
                </div>

                <!-- Contribution Graph -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/></svg> Contribution Graph</h3>
                    <div id="contribution-chart-container" style="position: relative; height: 30vh;">
                        <canvas id="contribution-chart"></canvas>
                    </div>
                </div>

                <!-- Top Repositories -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Top Starred Repositories</h3>
                    <div id="top-repos" class="repos-grid"></div>
                </div>

                <!-- Recent Commits -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg> Recent Commits</h3>
                    <div id="recent-commits" class="commits-list"></div>
                </div>

                <!-- All Repositories -->
                <div class="profile-section">
                    <h3><svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg> All Repositories</h3>
                    <div id="all-repos" class="repos-grid"></div>
                </div>
            </div>
            
            <!-- API Documentation -->
            <div id="api-docs-container" style="margin-top: 3rem;">
                <h1>API Documentation</h1>
                <p>
                    This dashboard is powered by the GitHub Analytics API. You can use it directly in your own projects.
                    For interactive API exploration, see
                    <a href="/docs" style="color: var(--secondary-color);">Swagger UI</a> or
                    <a href="/redoc" style="color: var(--secondary-color);">ReDoc</a>.
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

                <div class="api-section">
                    <div class="section-header">
                        <h2>Pull Request & Organization Endpoints</h2>
                        <span class="section-toggle">&#9660;</span>
                    </div>
                    <div class="section-content">
                        <div class="endpoint">
                            <div class="endpoint-header">
                                <h2><span class="endpoint-method">GET</span><code class="path">/{username}/me/pulls</code> Get User's Pull Requests (Own Repos)</h2>
                                <span class="endpoint-toggle">+</span>
                            </div>
                            <div class="endpoint-content">
                                <p>Returns all pull requests created by the user in their own repositories, including their status (merged, closed, or open).</p>
                                <div class="note">
                                    <h3>Example Request</h3>
                                    <pre><code>GET /tashifkhan/me/pulls</code></pre>
                                </div>
                                <div class="response">
                                    <h3>Response</h3>
                                    <pre><code class="language-json">[
    {
        "repo": "RepoName",
        "number": 123,
        "title": "Fix bug in feature X",
        "state": "merged",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
        "closed_at": "2023-01-02T12:00:00Z",
        "merged_at": "2023-01-02T12:00:00Z",
        "user": "tashifkhan",
        "url": "https://github.com/tashifkhan/RepoName/pull/123",
        "body": "This PR fixes ..."
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
                                <h2><span class="endpoint-method">GET</span><code class="path">/{username}/org-contributions</code> Get Organizations Contributed To</h2>
                                <span class="endpoint-toggle">+</span>
                            </div>
                            <div class="endpoint-content">
                                <p>Returns all organizations where the user has contributed (via merged PRs), and the repositories they contributed to.</p>
                                <div class="note">
                                    <h3>Example Request</h3>
                                    <pre><code>GET /tashifkhan/org-contributions</code></pre>
                                </div>
                                <div class="response">
                                    <h3>Response</h3>
                                    <pre><code class="language-json">[
    {
        "org": "openai",
        "org_id": 123456,
        "org_url": "https://github.com/openai",
        "org_avatar_url": "https://avatars.githubusercontent.com/u/123456?v=4",
        "repos": ["repo1", "repo2"]
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
                                <h2><span class="endpoint-method">GET</span><code class="path">/{username}/prs</code> Get PRs Opened in Other People's Repos</h2>
                                <span class="endpoint-toggle">+</span>
                            </div>
                            <div class="endpoint-content">
                                <p>Returns all pull requests opened by the user in other people's repositories (not their own), including their status (merged, closed, or open).</p>
                                <div class="note">
                                    <h3>Example Request</h3>
                                    <pre><code>GET /tashifkhan/prs</code></pre>
                                </div>
                                <div class="response">
                                    <h3>Response</h3>
                                    <pre><code class="language-json">[
    {
        "repo": "OtherRepo",
        "number": 456,
        "title": "Add new feature",
        "state": "closed",
        "created_at": "2023-02-01T10:00:00Z",
        "updated_at": "2023-02-02T10:00:00Z",
        "closed_at": "2023-02-02T10:00:00Z",
        "merged_at": null,
        "user": "tashifkhan",
        "url": "https://github.com/otheruser/OtherRepo/pull/456",
        "body": "Implements ..."
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
                                <p>Retrieves detailed information for each of the user's public repositories, including README content (Base64 encoded), languages, commit count, and stars count.</p>
                                
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
        "stars": 25,
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
                                <h2><span class="endpoint-method">GET</span><code class="path">/{username}/stars</code> Get User's Stars Information</h2>
                                <span class="endpoint-toggle">+</span>
                            </div>
                            <div class="endpoint-content">
                                <p>Retrieves stars information for a user's repositories including total stars and detailed repository information. Repositories are sorted by star count (highest first).</p>
                                
                                <div class="note">
                                    <h3>Example Request</h3>
                                    <pre><code>GET /tashifkhan/stars</code></pre>
                                </div>

                                <div class="response">
                                    <h3>Response</h3>
                                    <pre><code class="language-json">{
    "total_stars": 150,
    "repositories": [
        {
            "name": "RepoName",
            "description": "A popular project",
            "stars": 100,
            "url": "https://github.com/user/repo",
            "language": "Python",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-12-01T00:00:00Z"
        }
    ]
}</code></pre>
                                </div>

                                <div class="error-response">
                                    <h3>Error Responses</h3>
                                    <p><code>404</code> - User not found or API error</p>
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
                    
                    // Allow Enter key to submit form
                    const input = document.getElementById('github-username');
                    if (input) {
                        input.addEventListener('keypress', function(e) {
                            if (e.key === 'Enter') {
                                stalkGitHubUser();
                            }
                        });
                        
                        // Show dropdown on focus
                        input.addEventListener('focus', function() {
                            showDropdown();
                        });
                        
                        // Hide dropdown when clicking outside
                        document.addEventListener('click', function(e) {
                            const inputContainer = document.querySelector('.input-container');
                            if (!inputContainer.contains(e.target)) {
                                hideDropdown();
                            }
                        });
                    }
                    
                    // Initialize user history dropdown
                    updateHistoryDropdown();
                    
                    // Add event listener for clear history button
                    const clearBtn = document.getElementById('clear-history');
                    if (clearBtn) {
                        clearBtn.addEventListener('click', clearUserHistory);
                    }
                    
                    // Add event listener for clear all button in dropdown
                    const clearAllBtn = document.getElementById('clear-all-history');
                    if (clearAllBtn) {
                        clearAllBtn.addEventListener('click', clearUserHistory);
                    }
                });
                
                // User History Management
                const USER_HISTORY_KEY = 'github_username_history';
                const MAX_HISTORY_ITEMS = 10;
                
                function loadUserHistory() {
                    try {
                        const history = localStorage.getItem(USER_HISTORY_KEY);
                        return history ? JSON.parse(history) : [];
                    } catch (error) {
                        console.error('Error loading user history:', error);
                        return [];
                    }
                }
                
                function saveUserHistory(username) {
                    if (!username || username.trim() === '') return;
                    
                    try {
                        const history = loadUserHistory();
                        const usernameLower = username.toLowerCase().trim();
                        
                        // Remove if already exists (to move to top)
                        const filteredHistory = history.filter(item => item.toLowerCase() !== usernameLower);
                        
                        // Add to beginning
                        filteredHistory.unshift(username.trim());
                        
                        // Keep only the latest MAX_HISTORY_ITEMS
                        const trimmedHistory = filteredHistory.slice(0, MAX_HISTORY_ITEMS);
                        
                        localStorage.setItem(USER_HISTORY_KEY, JSON.stringify(trimmedHistory));
                        updateHistoryDropdown();
                    } catch (error) {
                        console.error('Error saving user history:', error);
                    }
                }
                
                function updateHistoryDropdown() {
                    const historyList = document.getElementById('history-list');
                    const history = loadUserHistory();
                    
                    if (!historyList) return;
                    
                    // Clear existing items
                    historyList.innerHTML = '';
                    
                    if (history.length === 0) {
                        historyList.innerHTML = '<div class="history-empty">No recent searches</div>';
                        return;
                    }
                    
                    // Add history items
                    history.forEach((username, index) => {
                        const item = document.createElement('div');
                        item.className = 'history-item';
                        item.innerHTML = `
                            <span class="history-username">${username}</span>
                            <button type="button" class="history-delete-btn" data-index="${index}" title="Remove from history">
                                <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                                </svg>
                            </button>
                        `;
                        
                        // Add click event to select username
                        item.addEventListener('click', (e) => {
                            if (!e.target.closest('.history-delete-btn')) {
                                document.getElementById('github-username').value = username;
                                hideDropdown();
                                stalkGitHubUser();
                            }
                        });
                        
                        // Add delete event
                        const deleteBtn = item.querySelector('.history-delete-btn');
                        deleteBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            removeFromHistory(index);
                        });
                        
                        historyList.appendChild(item);
                    });
                }
                
                function showDropdown() {
                    const dropdown = document.getElementById('history-dropdown');
                    if (dropdown) {
                        dropdown.classList.add('active');
                    }
                }
                
                function hideDropdown() {
                    const dropdown = document.getElementById('history-dropdown');
                    if (dropdown) {
                        dropdown.classList.remove('active');
                    }
                }
                
                function removeFromHistory(index) {
                    try {
                        const history = loadUserHistory();
                        history.splice(index, 1);
                        localStorage.setItem(USER_HISTORY_KEY, JSON.stringify(history));
                        updateHistoryDropdown();
                    } catch (error) {
                        console.error('Error removing from history:', error);
                    }
                }
                
                function clearUserHistory() {
                    try {
                        localStorage.removeItem(USER_HISTORY_KEY);
                        updateHistoryDropdown();
                        hideDropdown();
                        
                        // Show feedback
                        const clearBtn = document.getElementById('clear-history');
                        if (clearBtn) {
                            const originalTitle = clearBtn.getAttribute('title');
                            clearBtn.setAttribute('title', 'History cleared!');
                            clearBtn.style.color = 'var(--secondary-color)';
                            
                            setTimeout(() => {
                                clearBtn.setAttribute('title', originalTitle);
                                clearBtn.style.color = '';
                            }, 2000);
                        }
                    } catch (error) {
                        console.error('Error clearing user history:', error);
                    }
                }
                
                // GitHub Profile Stalker functionality
                async function stalkGitHubUser() {
                    const usernameInput = document.getElementById('github-username');
                    if (!usernameInput) {
                        console.error('Username input not found');
                        return;
                    }
                    
                    const username = usernameInput.value.trim();
                    if (!username) {
                        alert('Please enter a GitHub username');
                        return;
                    }
                    
                    // Save to history
                    saveUserHistory(username);
                    
                    const loading = document.getElementById('loading');
                    const results = document.getElementById('profile-results');
                    
                    if (!loading || !results) {
                        console.error('Required DOM elements not found');
                        return;
                    }
                    
                    // Show loading
                    loading.style.display = 'block';
                    results.style.display = 'none';
                    
                    try {
                        // Fetch all data in parallel
                        const [statsResponse, reposResponse, starsResponse, commitsResponse] = await Promise.all([
                            fetch(`/${username}/stats`),
                            fetch(`/${username}/repos`),
                            fetch(`/${username}/stars`),
                            fetch(`/${username}/commits`)
                        ]);
                        
                        const stats = await statsResponse.json();
                        const repos = await reposResponse.json();
                        const stars = await starsResponse.json();
                        const commits = await commitsResponse.json();
                        
                        // Display results
                        displayProfileResults(username, stats, repos, stars, commits);
                        
                    } catch (error) {
                        console.error('Error fetching data:', error);
                        showError('Failed to fetch GitHub data. Please check the username and try again.');
                    } finally {
                        if (loading) {
                            loading.style.display = 'none';
                        }
                    }
                }
                
                function displayProfileResults(username, stats, repos, stars, commits) {
                    const results = document.getElementById('profile-results');
                    
                    // Update profile overview cards with null checks
                    const elements = {
                        'total-commits': document.getElementById('total-commits'),
                        'longest-streak': document.getElementById('longest-streak'),
                        'current-streak': document.getElementById('current-streak'),
                        'profile-views': document.getElementById('profile-views'),
                        'total-stars': document.getElementById('total-stars'),
                        'total-repos': document.getElementById('total-repos')
                    };
                    
                    if (stats.status === 'success') {
                        if (elements['total-commits']) elements['total-commits'].textContent = stats.totalCommits || 0;
                        if (elements['longest-streak']) elements['longest-streak'].textContent = stats.longestStreak || 0;
                        if (elements['current-streak']) elements['current-streak'].textContent = stats.currentStreak || 0;
                        if (elements['profile-views']) elements['profile-views'].textContent = stats.profile_visitors || 0;
                        if (elements['total-stars']) elements['total-stars'].textContent = stars.total_stars || 0;
                        if (elements['total-repos']) elements['total-repos'].textContent = repos.length || 0;
                    } else {
                        // Handle error case
                        Object.values(elements).forEach(el => {
                            if (el) el.textContent = '0';
                        });
                    }
                    
                    // Display languages
                    displayLanguages(stats.topLanguages || []);
                    
                    // Display contribution graph
                    displayContributionGraph(stats.contributions || {});
                    
                    // Display top repositories
                    displayTopRepos(stars.repositories || []);
                    
                    // Display recent commits
                    displayRecentCommits(commits || []);
                    
                    // Display all repositories
                    displayAllRepos(username, repos || []);
                    
                    results.style.display = 'block';
                }
                
                function displayLanguages(languages) {
                    const container = document.getElementById('languages-chart');
                    if (!container) return;
                    
                    container.innerHTML = '';
                    
                    if (languages.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No language data available</p>';
                        return;
                    }
                    
                    languages.forEach(lang => {
                        const languageBar = document.createElement('div');
                        languageBar.className = 'language-bar';
                        languageBar.innerHTML = `
                            <div class="language-info">
                                <div class="language-color" style="background-color: ${getLanguageColor(lang.name)};"></div>
                                <span class="language-name">${lang.name}</span>
                            </div>
                            <span class="language-percentage">${lang.percentage.toFixed(1)}%</span>
                        `;
                        container.appendChild(languageBar);
                    });
                }
                
                var contributionChart;
                function displayContributionGraph(contributions) {
                    const container = document.getElementById('contribution-chart-container');
                    if (!container) return;

                    const canvas = document.getElementById('contribution-chart');
                    if (!canvas) return;
                    
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return;

                    if (contributionChart) {
                        contributionChart.destroy();
                    }

                    // Get theme colors from CSS variables
                    const styles = getComputedStyle(document.documentElement);
                    const textColor = styles.getPropertyValue('--text-color').trim();
                    const secondaryColor = styles.getPropertyValue('--secondary-color').trim();
                    const gridColor = 'rgba(136, 146, 176, 0.1)';

                    let allDays = [];

                    if (contributions && typeof contributions === 'object') {
                        const years = Object.keys(contributions).sort();
                        years.forEach(year => {
                            const yearData = contributions[year];
                            let weeks = [];
                            if (yearData?.data?.user?.contributionsCollection?.contributionCalendar?.weeks) {
                                weeks = yearData.data.user.contributionsCollection.contributionCalendar.weeks;
                            } else if (yearData?.user?.contributionsCollection?.weeks) {
                                weeks = yearData.user.contributionsCollection.weeks;
                            } else if (Array.isArray(yearData)) {
                                weeks = yearData;
                            }

                            weeks.forEach(week => {
                                if (week.contributionDays) {
                                    week.contributionDays.forEach(day => {
                                        allDays.push({
                                            date: day.date,
                                            count: day.contributionCount,
                                        });
                                    });
                                }
                            });
                        });
                    }

                    if (allDays.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No contribution data available.</p>';
                        return;
                    }

                    allDays.sort((a, b) => new Date(a.date) - new Date(b.date));
                    
                    // Show data for the last year, up to today
                    const today = new Date();
                    const oneYearAgo = new Date();
                    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                    
                    const lastYearDays = allDays.filter(day => {
                        const dayDate = new Date(day.date);
                        return dayDate >= oneYearAgo && dayDate <= today;
                    });

                    if (lastYearDays.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No contribution data available for the last year.</p>';
                        return;
                    }

                    const labels = lastYearDays.map(day => {
                        const date = new Date(day.date);
                        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
                    });

                    const data = lastYearDays.map(day => day.count);

                    contributionChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Contributions',
                                data: data,
                                borderColor: secondaryColor,
                                backgroundColor: 'rgba(100, 255, 218, 0.1)',
                                fill: true,
                                borderWidth: 2,
                                pointBackgroundColor: secondaryColor,
                                pointRadius: 3,
                                pointHoverRadius: 5,
                                tension: 0.3
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: false,
                                },
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    grid: {
                                        color: gridColor
                                    },
                                    ticks: {
                                        color: textColor,
                                    },
                                    title: {
                                        display: true,
                                        text: 'Contributions',
                                        color: textColor
                                    }
                                },
                                x: {
                                    grid: {
                                        display: false
                                    },
                                    ticks: {
                                        color: textColor,
                                        autoSkip: true,
                                        maxTicksLimit: 20
                                    },
                                    title: {
                                        display: true,
                                        text: 'Date',
                                        color: textColor
                                    }
                                }
                            }
                        }
                    });
                }
                
                function displayTopRepos(repos) {
                    const container = document.getElementById('top-repos');
                    if (!container) return;
                    
                    container.innerHTML = '';
                    
                    if (repos.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No repository data available</p>';
                        return;
                    }
                    
                    // Show top 6 repositories
                    repos.slice(0, 6).forEach(repo => {
                        const repoCard = document.createElement('div');
                        repoCard.className = 'repo-card';
                        repoCard.innerHTML = `
                            <div class="repo-header">
                                <a href="${repo.url}" target="_blank" class="repo-name">${repo.name}</a>
                                <span class="repo-stars">
                                    <svg class="icon" viewBox="0 0 24 24" fill="currentColor" style="width: 0.8rem; height: 0.8rem; margin-right: 0.25rem;"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                                    ${repo.stars}
                                </span>
                            </div>
                            <div class="repo-description">${repo.description || 'No description available'}</div>
                            <div class="repo-meta">
                                <span class="repo-language">
                                    <div class="repo-language-dot" style="background-color: ${getLanguageColor(repo.language)};"></div>
                                    ${repo.language || 'Unknown'}
                                </span>
                                <span>Updated ${formatDate(repo.updated_at)}</span>
                                ${repo.homepage ? `<span><a href="${repo.homepage}" target="_blank" style="color: var(--secondary-color);"><svg class="icon" viewBox="0 0 24 24" fill="currentColor" style="width: 0.8rem; height: 0.8rem; margin-right: 0.25rem;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>Live Site</a></span>` : ''}
                            </div>
                        `;
                        container.appendChild(repoCard);
                    });
                }
                
                function displayRecentCommits(commits) {
                    const container = document.getElementById('recent-commits');
                    if (!container) return;
                    
                    container.innerHTML = '';
                    
                    if (commits.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No commit data available</p>';
                        return;
                    }
                    
                    // Show recent 10 commits
                    commits.slice(0, 10).forEach(commit => {
                        const commitItem = document.createElement('div');
                        commitItem.className = 'commit-item';
                        commitItem.innerHTML = `
                            <div class="commit-header">
                                <span class="commit-repo">${commit.repo}</span>
                                <span class="commit-date">${formatDate(commit.timestamp)}</span>
                            </div>
                            <div class="commit-message">${commit.message}</div>
                        `;
                        container.appendChild(commitItem);
                    });
                }
                
                function displayAllRepos(username, repos) {
                    const container = document.getElementById('all-repos');
                    if (!container) return;
                    
                    container.innerHTML = '';
                    
                    if (repos.length === 0) {
                        container.innerHTML = '<p style="text-align: center; color: var(--text-color);">No repository data available</p>';
                        return;
                    }
                    
                    repos.forEach(repo => {
                        const repoCard = document.createElement('div');
                        repoCard.className = 'repo-card';
                        repoCard.innerHTML = `
                            <div class="repo-header">
                                <a href="https://github.com/${username}/${repo.title}" target="_blank" class="repo-name">${repo.title}</a>
                                <span class="repo-stars">
                                    <svg class="icon" viewBox="0 0 24 24" fill="currentColor" style="width: 0.8rem; height: 0.8rem; margin-right: 0.25rem;"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                                    ${repo.stars || 0}
                                </span>
                            </div>
                            <div class="repo-description">${repo.description || 'No description available'}</div>
                            <div class="repo-meta">
                                <span class="repo-language">
                                    <div class="repo-language-dot" style="background-color: ${getLanguageColor(repo.languages?.[0])};"></div>
                                    ${repo.languages?.[0] || 'Unknown'}
                                </span>
                                <span>${repo.num_commits || 0} commits</span>
                                ${repo.live_website_url ? `<span><a href="${repo.live_website_url}" target="_blank" style="color: var(--secondary-color);"><svg class="icon" viewBox="0 0 24 24" fill="currentColor" style="width: 0.8rem; height: 0.8rem; margin-right: 0.25rem;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>Live Site</a></span>` : ''}
                            </div>
                        `;
                        container.appendChild(repoCard);
                    });
                }
                
                function getLanguageColor(language) {
                    const colors = {
                        'Python': '#3572A5',
                        'JavaScript': '#f1e05a',
                        'TypeScript': '#2b7489',
                        'Java': '#b07219',
                        'C++': '#f34b7d',
                        'C#': '#178600',
                        'PHP': '#4F5D95',
                        'Ruby': '#701516',
                        'Go': '#00ADD8',
                        'Rust': '#dea584',
                        'Swift': '#ffac45',
                        'Kotlin': '#F18E33',
                        'Scala': '#c22d40',
                        'HTML': '#e34c26',
                        'CSS': '#563d7c',
                        'Shell': '#89e051',
                        'Dockerfile': '#384d54',
                        'Vue': '#2c3e50',
                        'React': '#61dafb',
                        'Angular': '#dd0031'
                    };
                    return colors[language] || '#6f42c1';
                }
                
                function formatDate(dateString) {
                    if (!dateString) return 'Unknown';
                    const date = new Date(dateString);
                    return date.toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric' 
                    });
                }
                
                function showError(message) {
                    const results = document.getElementById('profile-results');
                    if (!results) {
                        console.error('Results container not found');
                        return;
                    }
                    results.innerHTML = `<div class="error-message">${message}</div>`;
                    results.style.display = 'block';
                }
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
