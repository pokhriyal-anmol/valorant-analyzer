# Valorant Performance Analyzer v3.0

An interactive web app that analyzes your Valorant competitive performance using the Henrik API, with optional AI-powered coaching via OpenRouter.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-green?logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Player Search** — analyze any player by name/tag, no CLI required
- **8 Dashboard Tabs** — Overview, Agents, Maps, Trends, Weaknesses, AI Analysis, Match History, Resources
- **Performance Grading** — S/A/B/C/D/F grades based on rank-specific benchmarks with detailed reasoning
- **AI Coaching** — full profile analysis and per-match coaching via OpenRouter (Gemini 2.5 Flash)
- **Interactive Charts** — radar, bar, and line charts rendered with Canvas 2D
- **Match History** — expandable rows with shot distribution, damage stats, and grade breakdowns

## Requirements

- Python 3.8+
- A [Henrik API](https://docs.henrikdev.xyz/) key (free tier: 30 req/min)
- Optional: an [OpenRouter](https://openrouter.ai/) API key for AI analysis (free tier available)

## Quick Start (Local)

```bash
git clone https://github.com/YOUR_USERNAME/valorant-analyzer.git
cd valorant-analyzer
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## Usage

1. Open the app in your browser
2. Enter a player name, tag (e.g., `preecious` / `prime`), and select a region
3. Paste your Henrik API key
4. Optionally add your OpenRouter key for AI-powered analysis
5. Click **Analyze** and wait for data fetching (~30-60 seconds depending on match count)

## Free Hosting Options

You can deploy this app for free on any of the following platforms:

### Render (Recommended)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Settings: **Build Command** = `pip install -r requirements.txt`, **Start Command** = `gunicorn app:app`
5. Select the **Free** tier and deploy

### Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects Flask via `Procfile`
4. It deploys automatically. Free tier includes $5/month credit

### Koyeb

1. Push this repo to GitHub
2. Go to [koyeb.com](https://www.koyeb.com) → Create App → GitHub
3. Select your repo, set **Start Command** = `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Free tier includes one nano instance

### Fly.io

1. Install the Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Run `fly launch` in the project directory
3. Deploy with `fly deploy`
4. Free tier includes 3 shared-cpu VMs

## Architecture

Single-file Flask backend (`app.py`) serving a self-contained HTML SPA (`templates/index.html`). All API calls (Henrik, OpenRouter) happen server-side in Python. The frontend communicates via three JSON endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves the SPA |
| `/api/analyze` | POST | Fetches all player data from Henrik API, processes stats |
| `/api/ai-analysis` | POST | Calls OpenRouter for full AI coaching report |
| `/api/match-analysis` | POST | Calls OpenRouter for per-match coaching |

## API Keys

- **Henrik API**: Get one at [docs.henrikdev.xyz](https://docs.henrikdev.xyz/). Free tier allows 30 requests/minute.
- **OpenRouter**: Get one at [openrouter.ai](https://openrouter.ai/). Free tier includes access to `google/gemini-2.5-flash`.

> **Note**: API keys are entered in the browser and sent to the server per-request. They are never stored on the server.

## Project Structure

```
valorant-analyzer/
├── app.py                 # Flask server with all backend logic
├── templates/
│   └── index.html         # Full SPA frontend
├── valorant_analyzer.py   # Original CLI version (standalone)
├── requirements.txt       # Python dependencies
├── Procfile               # Process file for deployment platforms
├── runtime.txt            # Python version specification
├── LICENSE                # MIT License
└── README.md              # This file
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)
