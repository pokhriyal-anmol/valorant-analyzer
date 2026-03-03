"""
Valorant Performance Analyzer Flask Backend v2.0
AI-Powered analysis tool using Henrik API + OpenRouter
"""

from flask import Flask, render_template, request, jsonify
import requests
import json
import time
import html as html_module
import math
from typing import Dict, List, Optional
from collections import defaultdict
from statistics import mean, stdev

# ============ CONSTANTS ============
HENRIK_BASE_URL = "https://api.henrikdev.xyz/valorant"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
RATE_LIMIT_DELAY = 2.5
MAX_PAGES = 50

RANK_BENCHMARKS = {
    'Iron':      {'kd': 0.70, 'hs': 14, 'adr': 110, 'acs': 160, 'winrate': 50, 'kpr': 0.55, 'dpr': 0.78, 'apr': 0.20},
    'Bronze':    {'kd': 0.80, 'hs': 17, 'adr': 120, 'acs': 175, 'winrate': 50, 'kpr': 0.62, 'dpr': 0.76, 'apr': 0.22},
    'Silver':    {'kd': 0.90, 'hs': 20, 'adr': 130, 'acs': 190, 'winrate': 50, 'kpr': 0.68, 'dpr': 0.74, 'apr': 0.25},
    'Gold':      {'kd': 0.95, 'hs': 23, 'adr': 140, 'acs': 200, 'winrate': 51, 'kpr': 0.72, 'dpr': 0.73, 'apr': 0.27},
    'Platinum':  {'kd': 1.05, 'hs': 26, 'adr': 150, 'acs': 215, 'winrate': 51, 'kpr': 0.77, 'dpr': 0.72, 'apr': 0.29},
    'Diamond':   {'kd': 1.15, 'hs': 29, 'adr': 160, 'acs': 230, 'winrate': 52, 'kpr': 0.82, 'dpr': 0.70, 'apr': 0.32},
    'Ascendant': {'kd': 1.25, 'hs': 32, 'adr': 170, 'acs': 245, 'winrate': 53, 'kpr': 0.87, 'dpr': 0.68, 'apr': 0.35},
    'Immortal':  {'kd': 1.35, 'hs': 35, 'adr': 180, 'acs': 260, 'winrate': 54, 'kpr': 0.92, 'dpr': 0.65, 'apr': 0.38},
    'Radiant':   {'kd': 1.50, 'hs': 38, 'adr': 195, 'acs': 280, 'winrate': 55, 'kpr': 1.00, 'dpr': 0.62, 'apr': 0.42}
}

TIER_TO_RANK = {
    0: 'Unranked', 3: 'Iron 1', 4: 'Iron 2', 5: 'Iron 3',
    6: 'Bronze 1', 7: 'Bronze 2', 8: 'Bronze 3',
    9: 'Silver 1', 10: 'Silver 2', 11: 'Silver 3',
    12: 'Gold 1', 13: 'Gold 2', 14: 'Gold 3',
    15: 'Platinum 1', 16: 'Platinum 2', 17: 'Platinum 3',
    18: 'Diamond 1', 19: 'Diamond 2', 20: 'Diamond 3',
    21: 'Ascendant 1', 22: 'Ascendant 2', 23: 'Ascendant 3',
    24: 'Immortal 1', 25: 'Immortal 2', 26: 'Immortal 3',
    27: 'Radiant'
}

app = Flask(__name__)


# ============ API HELPERS ============
class HenrikAPI:
    def __init__(self, apikey: str):
        self.headers = {'Authorization': apikey}

    def _get(self, endpoint: str) -> Optional[Dict]:
        try:
            time.sleep(RATE_LIMIT_DELAY)
            resp = requests.get(endpoint, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                time.sleep(30)
                return self._get(endpoint)
            else:
                return None
        except requests.exceptions.RequestException:
            return None


# ============ DATA FETCHING ============
def fetch_account(api, name, tag):
    data = api._get(f"{HENRIK_BASE_URL}/v2/account/{name}/{tag}")
    if data and 'data' in data:
        return data['data']
    return None


def fetch_mmr(api, region, name, tag):
    data = api._get(f"{HENRIK_BASE_URL}/v2/mmr/{region}/{name}/{tag}")
    if data and 'data' in data:
        return data['data']
    return None


def fetch_mmr_history(api, region, name, tag):
    data = api._get(f"{HENRIK_BASE_URL}/v1/mmr-history/{region}/{name}/{tag}")
    if data and 'data' in data:
        return data['data']
    return []


def fetch_all_matches(api, region, name, tag):
    all_matches = []
    total_available = None

    for page in range(1, MAX_PAGES + 1):
        url = f"{HENRIK_BASE_URL}/v1/stored-matches/{region}/{name}/{tag}?mode=competitive&size=20"
        if page > 1:
            url += f"&page={page}"

        data = api._get(url)
        if not data or 'data' not in data:
            break

        matches = data['data']
        if total_available is None:
            total_available = data.get('results', {}).get('total', len(matches))

        if not matches:
            break

        all_matches.extend(matches)

        if len(all_matches) >= total_available or len(matches) < 20:
            break

    return all_matches


# ============ DATA PROCESSING ============
def process_match(match, puuid):
    try:
        meta = match.get('meta', {})
        stats = match.get('stats', {})
        teams = match.get('teams', {})

        map_name = meta.get('map', {}).get('name', 'Unknown')
        started_at = meta.get('started_at', '')

        player_team = stats.get('team', '').lower()
        other_team = 'blue' if player_team == 'red' else 'red'
        team_rounds = teams.get(player_team, 0)
        other_rounds = teams.get(other_team, 0)
        rounds_played = team_rounds + other_rounds
        if rounds_played == 0:
            return None

        won = team_rounds > other_rounds
        kills = stats.get('kills', 0)
        deaths = stats.get('deaths', 0)
        assists = stats.get('assists', 0)
        score = stats.get('score', 0)
        dmg_dealt = stats.get('damage', {}).get('made', 0)
        dmg_recv = stats.get('damage', {}).get('received', 0)
        hs = stats.get('shots', {}).get('head', 0)
        bs = stats.get('shots', {}).get('body', 0)
        ls = stats.get('shots', {}).get('leg', 0)
        agent = stats.get('character', {}).get('name', 'Unknown')
        tier = stats.get('tier', 0)
        total_shots = hs + bs + ls

        return {
            'map': map_name, 'date': started_at, 'agent': agent, 'won': won,
            'kills': kills, 'deaths': deaths, 'assists': assists, 'score': score,
            'kd': round(kills / deaths, 2) if deaths > 0 else float(kills),
            'adr': round(dmg_dealt / rounds_played, 1),
            'acs': round(score / rounds_played, 1),
            'hs_pct': round(hs / total_shots * 100, 1) if total_shots > 0 else 0,
            'kpr': round(kills / rounds_played, 2),
            'dpr': round(deaths / rounds_played, 2),
            'apr': round(assists / rounds_played, 2),
            'dmg_dealt': dmg_dealt, 'dmg_recv': dmg_recv,
            'headshots': hs, 'bodyshots': bs, 'legshots': ls,
            'rounds': rounds_played, 'tier': tier,
            'tier_name': TIER_TO_RANK.get(tier, f'Tier {tier}')
        }
    except Exception:
        return None


def process_all_matches(raw_matches, puuid):
    processed = [r for r in (process_match(m, puuid) for m in raw_matches) if r]
    return processed


def calculate_stats(matches):
    if not matches:
        return {}

    total = len(matches)
    wins = sum(1 for m in matches if m['won'])
    total_kills = sum(m['kills'] for m in matches)
    total_deaths = sum(m['deaths'] for m in matches)
    total_assists = sum(m['assists'] for m in matches)
    total_rounds = sum(m['rounds'] for m in matches)
    total_dmg = sum(m['dmg_dealt'] for m in matches)
    total_hs = sum(m['headshots'] for m in matches)
    total_bs = sum(m['bodyshots'] for m in matches)
    total_ls = sum(m['legshots'] for m in matches)
    total_shots = total_hs + total_bs + total_ls

    # Per-agent
    agents = defaultdict(lambda: {'matches': 0, 'wins': 0, 'kills': 0, 'deaths': 0, 'rounds': 0})
    for m in matches:
        a = agents[m['agent']]
        a['matches'] += 1
        a['wins'] += int(m['won'])
        a['kills'] += m['kills']
        a['deaths'] += m['deaths']
        a['rounds'] += m['rounds']

    agent_stats = sorted([{
        'agent': name,
        'matches': d['matches'],
        'winrate': round(d['wins'] / d['matches'] * 100, 1),
        'kd': round(d['kills'] / max(d['deaths'], 1), 2),
        'kpr': round(d['kills'] / max(d['rounds'], 1), 2)
    } for name, d in agents.items()], key=lambda x: x['matches'], reverse=True)

    # Per-map
    maps = defaultdict(lambda: {'matches': 0, 'wins': 0})
    for m in matches:
        maps[m['map']]['matches'] += 1
        maps[m['map']]['wins'] += int(m['won'])

    map_stats = sorted([{
        'map': name,
        'matches': d['matches'],
        'winrate': round(d['wins'] / d['matches'] * 100, 1)
    } for name, d in maps.items()], key=lambda x: x['matches'], reverse=True)

    # Consistency & streaks
    kds = [m['kd'] for m in matches]
    adrs = [m['adr'] for m in matches]
    max_win = max_loss = cur_win = cur_loss = 0
    for m in matches:
        if m['won']:
            cur_win += 1; cur_loss = 0
        else:
            cur_loss += 1; cur_win = 0
        max_win = max(max_win, cur_win)
        max_loss = max(max_loss, cur_loss)

    # Recent form
    recent = matches[:10]
    recent_wins = sum(1 for m in recent if m['won'])

    return {
        'total_matches': total, 'wins': wins, 'losses': total - wins,
        'winrate': round(wins / total * 100, 1),
        'total_kills': total_kills, 'total_deaths': total_deaths,
        'total_assists': total_assists, 'total_rounds': total_rounds,
        'kd': round(total_kills / max(total_deaths, 1), 2),
        'adr': round(total_dmg / max(total_rounds, 1), 1),
        'acs': round(mean([m['acs'] for m in matches]), 1),
        'hs_pct': round(total_hs / max(total_shots, 1) * 100, 1),
        'kpr': round(total_kills / max(total_rounds, 1), 2),
        'dpr': round(total_deaths / max(total_rounds, 1), 2),
        'apr': round(total_assists / max(total_rounds, 1), 2),
        'kd_std': round(stdev(kds), 2) if len(kds) > 1 else 0,
        'adr_std': round(stdev(adrs), 1) if len(adrs) > 1 else 0,
        'agent_stats': agent_stats, 'map_stats': map_stats,
        'recent_wr': round(recent_wins / len(recent) * 100, 1) if recent else 0,
        'recent_kd': round(mean([m['kd'] for m in recent]), 2) if recent else 0,
        'recent_adr': round(mean([m['adr'] for m in recent]), 1) if recent else 0,
        'recent_acs': round(mean([m['acs'] for m in recent]), 1) if recent else 0,
        'max_win_streak': max_win, 'max_loss_streak': max_loss,
    }


def get_rank_name(rank_string):
    for rank in ['Radiant', 'Immortal', 'Ascendant', 'Diamond', 'Platinum', 'Gold', 'Silver', 'Bronze', 'Iron']:
        if rank in str(rank_string):
            return rank
    return 'Iron'


def calculate_grade(stats, benchmarks):
    ratios = [
        stats.get('kd', 0) / max(benchmarks.get('kd', 1), 0.01),
        stats.get('adr', 0) / max(benchmarks.get('adr', 1), 0.01),
        stats.get('hs_pct', 0) / max(benchmarks.get('hs', 1), 0.01),
        stats.get('winrate', 0) / max(benchmarks.get('winrate', 1), 0.01)
    ]
    avg = mean(ratios)
    if avg >= 1.3: return 'S'
    if avg >= 1.15: return 'A'
    if avg >= 1.0: return 'B'
    if avg >= 0.85: return 'C'
    if avg >= 0.70: return 'D'
    return 'F'


# ============ ANALYSIS ============
def analyze_weaknesses(stats, benchmarks, rank_name):
    weaknesses = []
    checks = [
        ('kd', 'kd', 'Kill/Death Ratio', 0.25, 0.10, 'Play deathmatch daily. Focus on crosshair placement and off-angles.', 'Valorant dueling tips crosshair placement'),
        ('adr', 'adr', 'Average Damage per Round', 20, 10, 'Practice spray control. Commit to fights instead of backing off.', 'Valorant spray control damage guide'),
        ('hs_pct', 'hs', 'Headshot Percentage', 8, 3, 'Aim trainer 20 min daily. Head-level crosshair placement always.', 'Valorant crosshair placement headshot'),
        ('winrate', 'winrate', 'Win Rate', 10, 5, 'Review demos. Focus on economy, team play, map control.', 'Valorant game sense guide'),
        ('kpr', 'kpr', 'Kills per Round', 0.15, 0.05, 'Watch pro POVs. Learn optimal peek timings.', 'Valorant pro player positioning'),
    ]
    for sk, bk, title, hg, mg, drill, yt in checks:
        val = stats.get(sk, 0)
        bench = benchmarks.get(bk, 0)
        if val < bench:
            gap = bench - val
            sev = 'HIGH' if gap > hg else 'MEDIUM' if gap > mg else 'LOW'
            weaknesses.append({'title': f'Below-Average {title}', 'description': f'Your {sk.upper()} is {val}, vs benchmark {bench} at {rank_name}.', 'severity': sev, 'metric': f'{val} vs {bench}', 'drill': drill, 'youtube_query': yt})

    if stats.get('kd_std', 0) > 0.5:
        weaknesses.append({'title': 'Inconsistent Performance', 'description': f'K/D std dev: {stats["kd_std"]}. High variance between games.', 'severity': 'MEDIUM', 'metric': f'Std Dev: {stats["kd_std"]}', 'drill': 'Play methodically. Avoid ego-peeking.', 'youtube_query': 'Valorant consistency tips'})

    for m in stats.get('map_stats', []):
        if m['matches'] >= 3 and m['winrate'] < 35:
            weaknesses.append({'title': f'Struggling on {m["map"]}', 'description': f'{m["winrate"]}% WR on {m["map"]} ({m["matches"]} games).', 'severity': 'HIGH', 'metric': f'{m["winrate"]}% ({m["matches"]}g)', 'drill': f'Study {m["map"]} lineups and defaults.', 'youtube_query': f'Valorant {m["map"]} guide'})
            break

    for a in stats.get('agent_stats', []):
        if a['matches'] >= 5 and a['winrate'] < 35:
            weaknesses.append({'title': f'Underperforming on {a["agent"]}', 'description': f'{a["winrate"]}% WR ({a["matches"]} games). Consider switching.', 'severity': 'MEDIUM', 'metric': f'{a["winrate"]}% ({a["matches"]}g)', 'drill': f'Watch {a["agent"]} guides or play stronger agents.', 'youtube_query': f'Valorant {a["agent"]} guide'})
            break

    return sorted(weaknesses, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(x['severity'], 3))


def generate_tips(stats, weaknesses, rank_name):
    tips = []
    if weaknesses:
        tips.append({'priority': 1, 'title': f'Fix: {weaknesses[0]["title"]}', 'description': weaknesses[0]['drill'], 'time': '30-45 min daily', 'category': 'Priority Fix'})
    agents = stats.get('agent_stats', [])
    if agents:
        tips.append({'priority': 2, 'title': f'Main {agents[0]["agent"]}', 'description': f'{agents[0]["matches"]} games played. Specialize for consistency.', 'time': '20 min daily', 'category': 'Agent Mastery'})
    tips.append({'priority': 3, 'title': 'Review Demos', 'description': 'Watch 3-5 recent losses for positioning mistakes.', 'time': '30 min', 'category': 'Analysis'})
    tips.append({'priority': 4, 'title': 'DM Warmup', 'description': '2-3 deathmatches before ranked. Crosshair placement focus.', 'time': '15-20 min', 'category': 'Warmup'})
    tips.append({'priority': 5, 'title': 'Map Study', 'description': 'Pick your weakest map and learn defaults/rotations.', 'time': '1 hr/week', 'category': 'Map Knowledge'})
    return tips


def generate_resources(weaknesses, rank_name):
    queries = set()
    for w in weaknesses[:4]:
        queries.add(w.get('youtube_query', ''))
    queries.add(f'Valorant {rank_name.lower()} rank up guide')
    queries.add('Valorant crosshair placement guide')
    return [{'title': q.title(), 'url': f"https://www.youtube.com/results?search_query={'+'.join(q.split())}", 'type': 'YouTube'} for q in sorted(queries) if q]


# ============ OPENROUTER AI ============
def get_ai_analysis(openrouter_key, model, stats, matches, rank_str, peak_str, mmr_history):
    agents_text = "\n".join([f"  {a['agent']}: {a['matches']}g, {a['winrate']}% WR, {a['kd']} K/D" for a in stats.get('agent_stats', [])[:10]])
    maps_text = "\n".join([f"  {m['map']}: {m['matches']}g, {m['winrate']}% WR" for m in stats.get('map_stats', [])[:10]])
    recent_text = "\n".join([f"  {'W' if m['won'] else 'L'} | {m['map']} | {m['agent']} | {m['kills']}/{m['deaths']}/{m['assists']} | {m['kd']} KD | {m['acs']} ACS" for m in matches[:10]])

    prompt = f"""You are an expert Valorant coach. Analyze this player's data and provide comprehensive, personalized coaching.

## Player Profile
- Rank: {rank_str} | Peak: {peak_str}
- {stats['total_matches']} competitive matches: {stats['wins']}W-{stats['losses']}L ({stats['winrate']}% WR)

## Core Stats
- K/D: {stats['kd']} | HS%: {stats['hs_pct']}% | ADR: {stats['adr']} | ACS: {stats['acs']}
- KPR: {stats['kpr']} | DPR: {stats['dpr']} | APR: {stats['apr']}
- K/D Consistency (std dev): {stats['kd_std']} | ADR Consistency: {stats['adr_std']}
- Max Win Streak: {stats['max_win_streak']} | Max Loss Streak: {stats['max_loss_streak']}

## Recent Form (Last 10)
- WR: {stats['recent_wr']}% | K/D: {stats['recent_kd']} | ADR: {stats['recent_adr']} | ACS: {stats['recent_acs']}

## Agent Performance
{agents_text}

## Map Performance
{maps_text}

## Last 10 Matches
{recent_text}

---

Provide:
### 1. Overall Assessment (2-3 paragraphs, specific numbers)
### 2. Top 5 Weaknesses (name, why it matters, stat, severity HIGH/MEDIUM/LOW)
### 3. Top 5 Improvement Priorities (ordered by impact, specific drills with time estimates)
### 4. Agent Advice (which to focus on, which to drop, why)
### 5. Map Advice (which maps need work, specific strategies)
### 6. 4-Week Improvement Plan (week-by-week with daily/weekly tasks)

Be direct and specific. Reference actual numbers. No generic advice."""

    try:
        resp = requests.post(OPENROUTER_URL,
            headers={'Authorization': f'Bearer {openrouter_key}', 'Content-Type': 'application/json', 'HTTP-Referer': 'valorant-analyzer', 'X-Title': 'Valorant Performance Analyzer'},
            json={'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 4000, 'temperature': 0.7},
            timeout=120
        )
        if resp.status_code == 200:
            content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                return content
            print(f"[AI] Empty content in response: {resp.json()}")
        else:
            print(f"[AI] OpenRouter returned {resp.status_code}: {resp.text[:500]}")
    except requests.exceptions.Timeout:
        print("[AI] OpenRouter request timed out after 120s")
    except Exception as e:
        print(f"[AI] Exception during OpenRouter call: {type(e).__name__}: {e}")
    return None


def format_ai_html(ai_text):
    """Convert markdown-formatted AI text to proper HTML."""
    if not ai_text:
        return "<p>AI analysis was not available.</p>"

    import re

    def process_inline(text):
        """Process inline markdown: bold, italic, code."""
        # Escape HTML first
        text = html_module.escape(text)
        # Bold italic ***text***
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        # Bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic *text* (but not inside words like file*name)
        text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<em>\1</em>', text)
        # Inline code `text`
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    lines = ai_text.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        s = line.strip()

        # Close list if we're no longer in one
        if in_list and not (s.startswith('- ') or s.startswith('* ') or (s and s[0].isdigit() and '.' in s[:4])):
            html_lines.append('</ul>')
            in_list = False

        if not s:
            if not in_list:
                html_lines.append('')
            continue

        # Headers (#### down to #)
        if s.startswith('#### '):
            html_lines.append(f'<h4>{process_inline(s[5:])}</h4>')
        elif s.startswith('### '):
            html_lines.append(f'<h3>{process_inline(s[4:])}</h3>')
        elif s.startswith('## '):
            html_lines.append(f'<h2>{process_inline(s[3:])}</h2>')
        elif s.startswith('# '):
            html_lines.append(f'<h2>{process_inline(s[2:])}</h2>')
        # Horizontal rule
        elif s in ('---', '***', '___'):
            html_lines.append('<hr>')
        # List items
        elif s.startswith('- ') or s.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{process_inline(s[2:])}</li>')
        elif s[0].isdigit() and '.' in s[:4]:
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            # Strip the number prefix like "1. " or "10. "
            content = re.sub(r'^\d+\.\s*', '', s)
            html_lines.append(f'<li>{process_inline(content)}</li>')
        # Regular paragraph
        else:
            html_lines.append(f'<p>{process_inline(s)}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


# ============ FLASK ROUTES ============
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        name = data.get('name')
        tag = data.get('tag')
        region = data.get('region')
        apikey = data.get('apikey')

        if not all([name, tag, region, apikey]):
            return jsonify({'error': 'Missing required fields: name, tag, region, apikey'}), 400

        api = HenrikAPI(apikey)

        account = fetch_account(api, name, tag)
        if not account:
            return jsonify({'error': 'Could not fetch account. Check name/tag and API key.'}), 400

        puuid = account.get('puuid')
        mmr = fetch_mmr(api, region, name, tag)
        if not mmr:
            return jsonify({'error': 'Could not fetch MMR data.'}), 400

        mmr_history = fetch_mmr_history(api, region, name, tag)
        raw_matches = fetch_all_matches(api, region, name, tag)

        if not raw_matches:
            return jsonify({'error': 'No competitive matches found.'}), 400

        matches = process_all_matches(raw_matches, puuid)
        if not matches:
            return jsonify({'error': 'Could not process matches.'}), 400

        stats = calculate_stats(matches)
        current_mmr = mmr.get('current_data', {}) if mmr else {}
        rank_str = current_mmr.get('currenttierpatched', 'Unranked')
        peak_str = (mmr.get('highest_rank', {}) if mmr else {}).get('patched_tier', 'Unknown')
        rank_name = get_rank_name(rank_str)
        benchmarks = RANK_BENCHMARKS.get(rank_name, RANK_BENCHMARKS['Iron'])
        grade = calculate_grade(stats, benchmarks)

        weaknesses = analyze_weaknesses(stats, benchmarks, rank_name)
        tips = generate_tips(stats, weaknesses, rank_name)
        resources = generate_resources(weaknesses, rank_name)

        current_mmr_obj = mmr.get('current_data', {}) if mmr else {}
        highest_rank_obj = mmr.get('highest_rank', {}) if mmr else {}

        response_data = {
            'player': {
                'name': f"{name}#{tag}",
                'rank': current_mmr_obj.get('currenttierpatched', 'Unranked'),
                'peak_rank': highest_rank_obj.get('patched_tier', 'Unknown'),
                'rr': current_mmr_obj.get('ranking_in_tier', 0),
                'elo': current_mmr_obj.get('elo', 0),
                'level': account.get('account_level', 0),
                'region': region.upper(),
                'grade': grade
            },
            'stats': stats,
            'matches': matches,
            'agent_stats': stats.get('agent_stats', []),
            'map_stats': stats.get('map_stats', []),
            'elo_history': [
                {'elo': h.get('elo', 0), 'rank': h.get('currenttierpatched', ''), 'rr_change': h.get('mmr_change_to_last_game', 0), 'map': h.get('map', {}).get('name', '')}
                for h in reversed(mmr_history)
            ] if mmr_history else [],
            'benchmarks': RANK_BENCHMARKS,
            'rank_name': rank_name,
            'weaknesses': weaknesses,
            'tips': tips,
            'resources': resources
        }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    try:
        data = request.get_json()
        stats = data.get('stats')
        matches = data.get('matches')
        rank_str = data.get('rank_str')
        peak_str = data.get('peak_str')
        mmr_history = data.get('mmr_history')
        openrouter_key = data.get('openrouter_key')
        model = data.get('model', 'google/gemini-2.5-flash')

        if not all([stats, matches, rank_str, openrouter_key]):
            return jsonify({'error': 'Missing required fields'}), 400

        ai_text = get_ai_analysis(openrouter_key, model, stats, matches, rank_str, peak_str, mmr_history or [])

        if not ai_text:
            return jsonify({'error': 'AI analysis unavailable — the OpenRouter request failed or timed out. Check your API key and try again.'}), 502

        ai_html = format_ai_html(ai_text)

        return jsonify({'analysis': ai_html}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/match-analysis', methods=['POST'])
def match_analysis():
    try:
        data = request.get_json()
        match = data.get('match')
        player_stats = data.get('player_stats')
        rank_name = data.get('rank_name')
        openrouter_key = data.get('openrouter_key')
        model = data.get('model', 'google/gemini-2.5-flash')

        if not all([match, player_stats, rank_name, openrouter_key]):
            return jsonify({'error': 'Missing required fields'}), 400

        bench = RANK_BENCHMARKS.get(rank_name, RANK_BENCHMARKS['Iron'])

        prompt = f"""You are a Valorant coach analyzing a single match performance.

## Match Details
- Map: {match.get('map', 'Unknown')}
- Agent: {match.get('agent', 'Unknown')}
- Result: {'WIN' if match.get('won') else 'LOSS'}
- K/D/A: {match.get('kills')}/{match.get('deaths')}/{match.get('assists')}
- K/D Ratio: {match.get('kd')}
- Headshot %: {match.get('hs_pct')}%
- ADR: {match.get('adr')}
- ACS: {match.get('acs')}
- Damage Dealt: {match.get('dmg_dealt')}
- Damage Received: {match.get('dmg_recv')}
- Rounds: {match.get('rounds')}

## Player Overall Stats
- K/D: {player_stats.get('kd')}
- HS%: {player_stats.get('hs_pct')}%
- ADR: {player_stats.get('adr')}
- Win Rate: {player_stats.get('winrate')}%

## Rank Benchmarks ({rank_name})
- K/D: {bench.get('kd')}
- HS%: {bench.get('hs')}%
- ADR: {bench.get('adr')}
- ACS: {bench.get('acs')}

---

Provide a coaching analysis with:
### 1. Match Grade (S/A/B/C/D/F) and Explanation
### 2. What Went Right (specific moments with numbers)
### 3. What Went Wrong (specific areas for improvement with numbers)
### 4. 3 Specific Things to Improve for Next Time (actionable drills)

Be specific, reference actual numbers from the match, and provide actionable feedback."""

        try:
            resp = requests.post(OPENROUTER_URL,
                headers={'Authorization': f'Bearer {openrouter_key}', 'Content-Type': 'application/json', 'HTTP-Referer': 'valorant-analyzer', 'X-Title': 'Valorant Performance Analyzer'},
                json={'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 2000, 'temperature': 0.7},
                timeout=60
            )
            if resp.status_code == 200:
                ai_text = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                if ai_text:
                    ai_html = format_ai_html(ai_text)
                    return jsonify({'analysis': ai_html}), 200
        except Exception:
            pass

        return jsonify({'error': 'OpenRouter API failed. Please check your API key and try again.'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
