#!/usr/bin/env python3
"""
Valorant Performance Analyzer v2.0
AI-Powered analysis tool using Henrik API + OpenRouter
"""

import requests
import json
import argparse
import time
import sys
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
                print("  Rate limited, waiting 30s...")
                time.sleep(30)
                return self._get(endpoint)
            else:
                print(f"  API error {resp.status_code}: {resp.text[:100]}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"  Request error: {e}")
            return None


# ============ DATA FETCHING ============
def fetch_account(api, name, tag):
    print(f"[1/4] Fetching account info for {name}#{tag}...")
    data = api._get(f"{HENRIK_BASE_URL}/v2/account/{name}/{tag}")
    if data and 'data' in data:
        d = data['data']
        print(f"  ✓ Level {d.get('account_level')}, Region: {d.get('region')}")
        return d
    print("  ✗ Failed")
    return None


def fetch_mmr(api, region, name, tag):
    print(f"[2/4] Fetching MMR data...")
    data = api._get(f"{HENRIK_BASE_URL}/v2/mmr/{region}/{name}/{tag}")
    if data and 'data' in data:
        d = data['data']
        current = d.get('current_data', {})
        print(f"  ✓ Rank: {current.get('currenttierpatched', 'Unranked')} ({current.get('ranking_in_tier', 0)}RR)")
        return d
    print("  ✗ Failed")
    return None


def fetch_mmr_history(api, region, name, tag):
    print(f"[3/4] Fetching MMR history...")
    data = api._get(f"{HENRIK_BASE_URL}/v1/mmr-history/{region}/{name}/{tag}")
    if data and 'data' in data:
        print(f"  ✓ {len(data['data'])} entries")
        return data['data']
    print("  ⚠ Could not fetch history")
    return []


def fetch_all_matches(api, region, name, tag):
    print(f"[4/4] Fetching all competitive matches...")
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
            print(f"  Total available: {total_available}")

        if not matches:
            break

        all_matches.extend(matches)
        print(f"  ✓ Page {page}: {len(matches)} matches (Total: {len(all_matches)})")

        if len(all_matches) >= total_available or len(matches) < 20:
            break

    print(f"  ✓ Fetched {len(all_matches)} matches")
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
    print(f"\nProcessed {len(processed)} matches")
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
    print("\n[AI] Requesting analysis from OpenRouter...")

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
            timeout=60
        )
        if resp.status_code == 200:
            content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                print(f"  ✓ AI analysis received ({len(content)} chars)")
                return content
        print(f"  ⚠ OpenRouter error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  ⚠ OpenRouter failed: {e}")
    return None


def format_ai_html(ai_text):
    if not ai_text:
        return "<p>AI analysis was not available.</p>"
    escaped = html_module.escape(ai_text)
    lines = escaped.split('\n')
    html_lines = []
    for line in lines:
        s = line.strip()
        if s.startswith('### '): html_lines.append(f'<h3 class="ai-heading">{s[4:]}</h3>')
        elif s.startswith('## '): html_lines.append(f'<h2 class="ai-heading">{s[3:]}</h2>')
        elif s.startswith('# '): html_lines.append(f'<h2 class="ai-heading">{s[2:]}</h2>')
        elif s.startswith('- ') or s.startswith('* '): html_lines.append(f'<li>{s[2:]}</li>')
        elif s and s[0].isdigit() and '.' in s[:3]: html_lines.append(f'<li>{s}</li>')
        elif s == '': html_lines.append('<br>')
        else:
            text = s
            while '**' in text:
                text = text.replace('**', '<strong>', 1)
                if '**' in text: text = text.replace('**', '</strong>', 1)
            html_lines.append(f'<p>{text}</p>')
    return '\n'.join(html_lines)


# ============ HTML GENERATION ============
def generate_html(player_name, player_tag, region, account, mmr, mmr_history,
                  matches, stats, weaknesses, tips, resources, ai_html, benchmarks, rank_name, grade):

    current_mmr = mmr.get('current_data', {}) if mmr else {}
    highest_rank = mmr.get('highest_rank', {}) if mmr else {}

    data_obj = {
        'player': {
            'name': f"{player_name}#{player_tag}",
            'rank': current_mmr.get('currenttierpatched', 'Unranked'),
            'peak_rank': highest_rank.get('patched_tier', 'Unknown'),
            'rr': current_mmr.get('ranking_in_tier', 0),
            'elo': current_mmr.get('elo', 0),
            'level': account.get('account_level', 0) if account else 0,
            'region': region.upper(),
            'grade': grade
        },
        'stats': stats,
        'matches': matches[:20],
        'all_matches': matches,
        'agent_stats': stats.get('agent_stats', []),
        'map_stats': stats.get('map_stats', []),
        'elo_history': [
            {'elo': h.get('elo', 0), 'rank': h.get('currenttierpatched', ''), 'rr_change': h.get('mmr_change_to_last_game', 0), 'map': h.get('map', {}).get('name', '')}
            for h in reversed(mmr_history)
        ] if mmr_history else [],
        'benchmarks': benchmarks,
        'rank_name': rank_name
    }

    analysis_obj = {'weaknesses': weaknesses, 'tips': tips, 'resources': resources}

    data_json = json.dumps(data_obj, default=str)
    analysis_json = json.dumps(analysis_obj, default=str)

    # Use placeholder replacement (NOT .format()) to avoid brace escaping issues
    template = _get_html_template()
    html = template.replace('__DATA_JSON__', data_json)
    html = html.replace('__ANALYSIS_JSON__', analysis_json)
    html = html.replace('__AI_ANALYSIS_HTML__', ai_html.replace('`', '\\`').replace('${', '\\${'))
    return html


def _get_html_template():
    return open_template()


def open_template():
    """Return the HTML template as a string. Uses __PLACEHOLDER__ markers."""
    # This is kept as a raw string to avoid any escaping issues
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '    <meta charset="UTF-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '    <title>Valorant Performance Analyzer</title>\n'
        '    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
        '    <style>\n'
        '        :root {\n'
        '            --primary-bg: #0a0e27; --secondary-bg: #16213e; --tertiary-bg: #1f2937;\n'
        '            --accent-red: #ff4655; --accent-green: #00e5a0; --accent-gold: #ffce47;\n'
        '            --text-primary: #ffffff; --text-secondary: #a0a9b8; --text-tertiary: #6b7280;\n'
        '            --border-color: #2d3748; --success: #10b981; --warning: #f59e0b; --danger: #ef4444;\n'
        '        }\n'
        '        * { margin:0; padding:0; box-sizing:border-box; }\n'
        '        body { font-family:"Inter",sans-serif; background:var(--primary-bg); color:var(--text-primary); line-height:1.6; }\n'
        '        header { background:linear-gradient(135deg,#16213e,#0a0e27); border-bottom:2px solid var(--accent-red); padding:20px 30px; }\n'
        '        .header-inner { max-width:1400px; margin:0 auto; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:15px; }\n'
        '        .player-name { font-family:"Rajdhani",sans-serif; font-size:2rem; font-weight:700; background:linear-gradient(135deg,var(--accent-red),var(--accent-gold)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }\n'
        '        .player-meta { display:flex; gap:20px; flex-wrap:wrap; }\n'
        '        .meta-item { text-align:center; } .meta-label { font-size:0.7rem; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:1px; }\n'
        '        .meta-value { font-family:"Rajdhani",sans-serif; font-size:1.2rem; font-weight:600; }\n'
        '        .grade-badge { font-family:"Rajdhani",sans-serif; font-size:2.5rem; font-weight:700; width:60px; height:60px; display:flex; align-items:center; justify-content:center; border-radius:12px; border:2px solid; }\n'
        '        .grade-S{color:#ffd700;border-color:#ffd700;background:rgba(255,215,0,0.1)} .grade-A{color:#10b981;border-color:#10b981;background:rgba(16,185,129,0.1)}\n'
        '        .grade-B{color:#3b82f6;border-color:#3b82f6;background:rgba(59,130,246,0.1)} .grade-C{color:#f59e0b;border-color:#f59e0b;background:rgba(245,158,11,0.1)}\n'
        '        .grade-D{color:#ef4444;border-color:#ef4444;background:rgba(239,68,68,0.1)} .grade-F{color:#dc2626;border-color:#dc2626;background:rgba(220,38,38,0.1)}\n'
        '        .container { max-width:1400px; margin:0 auto; padding:20px; }\n'
        '        .tabs { display:flex; gap:5px; margin-bottom:20px; border-bottom:2px solid var(--border-color); overflow-x:auto; }\n'
        '        .tab-btn { padding:12px 18px; background:none; border:none; color:var(--text-secondary); cursor:pointer; font-size:0.85rem; font-weight:600; font-family:"Rajdhani",sans-serif; border-bottom:3px solid transparent; transition:all 0.2s; white-space:nowrap; }\n'
        '        .tab-btn:hover{color:var(--accent-green)} .tab-btn.active{color:var(--accent-red);border-bottom-color:var(--accent-red)}\n'
        '        .tab-content{display:none} .tab-content.active{display:block}\n'
        '        .stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:25px; }\n'
        '        .stat-card { background:var(--secondary-bg); border:1px solid var(--border-color); padding:16px; border-radius:8px; text-align:center; transition:border-color 0.2s; }\n'
        '        .stat-card:hover{border-color:var(--accent-red)}\n'
        '        .stat-label { font-size:0.7rem; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px; }\n'
        '        .stat-value { font-family:"Rajdhani",sans-serif; font-size:1.6rem; font-weight:700; }\n'
        '        .stat-bench { font-size:0.7rem; color:var(--text-tertiary); margin-top:4px; }\n'
        '        .good{color:var(--accent-green)} .bad{color:var(--accent-red)} .neutral{color:var(--accent-gold)}\n'
        '        .chart-box { background:var(--secondary-bg); border:1px solid var(--border-color); padding:20px; border-radius:8px; margin-bottom:20px; }\n'
        '        .chart-title { font-family:"Rajdhani",sans-serif; font-size:1.1rem; color:var(--text-secondary); margin-bottom:15px; text-transform:uppercase; letter-spacing:0.5px; }\n'
        '        canvas{width:100%!important;height:auto!important}\n'
        '        .two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px} @media(max-width:768px){.two-col{grid-template-columns:1fr}}\n'
        '        table{width:100%;border-collapse:collapse} th{background:var(--tertiary-bg);color:var(--text-secondary);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.5px;padding:10px 12px;text-align:left}\n'
        '        td{padding:10px 12px;border-bottom:1px solid var(--border-color);font-size:0.85rem} tr:hover{background:rgba(255,255,255,0.02)}\n'
        '        .wr-good{color:var(--success);font-weight:600} .wr-mid{color:var(--warning);font-weight:600} .wr-bad{color:var(--danger);font-weight:600}\n'
        '        .weakness-card{background:var(--secondary-bg);border:1px solid var(--border-color);border-radius:8px;padding:20px;margin-bottom:15px;border-left:4px solid}\n'
        '        .weakness-card.HIGH{border-left-color:var(--danger)} .weakness-card.MEDIUM{border-left-color:var(--warning)} .weakness-card.LOW{border-left-color:var(--success)}\n'
        '        .weakness-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}\n'
        '        .weakness-title{font-family:"Rajdhani",sans-serif;font-size:1.1rem;font-weight:600}\n'
        '        .severity-badge{font-size:0.7rem;font-weight:700;padding:3px 10px;border-radius:4px;text-transform:uppercase}\n'
        '        .severity-HIGH{background:rgba(239,68,68,0.2);color:#ef4444} .severity-MEDIUM{background:rgba(245,158,11,0.2);color:#f59e0b} .severity-LOW{background:rgba(16,185,129,0.2);color:#10b981}\n'
        '        .weakness-desc{color:var(--text-secondary);font-size:0.85rem;margin-bottom:8px}\n'
        '        .weakness-drill{color:var(--accent-green);font-size:0.8rem;font-style:italic}\n'
        '        .tip-card{background:var(--secondary-bg);border:1px solid var(--border-color);border-radius:8px;padding:16px;margin-bottom:12px;display:flex;gap:15px;align-items:flex-start}\n'
        '        .tip-num{font-family:"Rajdhani",sans-serif;font-size:1.5rem;font-weight:700;color:var(--accent-red);min-width:30px}\n'
        '        .tip-title{font-weight:600;margin-bottom:4px} .tip-desc{color:var(--text-secondary);font-size:0.85rem}\n'
        '        .tip-time{color:var(--accent-gold);font-size:0.75rem;margin-top:4px}\n'
        '        .resource-card{background:var(--secondary-bg);border:1px solid var(--border-color);border-radius:8px;padding:16px;margin-bottom:10px}\n'
        '        .resource-card a{color:var(--accent-red);text-decoration:none;font-weight:600} .resource-card a:hover{text-decoration:underline}\n'
        '        .ai-section{background:var(--secondary-bg);border:1px solid var(--border-color);border-radius:8px;padding:25px;line-height:1.8}\n'
        '        .ai-section h2,.ai-section h3{font-family:"Rajdhani",sans-serif;color:var(--accent-gold);margin:20px 0 10px;border-bottom:1px solid var(--border-color);padding-bottom:5px}\n'
        '        .ai-section h2{font-size:1.3rem} .ai-section h3{font-size:1.1rem;color:var(--accent-green)}\n'
        '        .ai-section p{color:var(--text-secondary);margin-bottom:8px;font-size:0.9rem}\n'
        '        .ai-section li{color:var(--text-secondary);margin-left:20px;margin-bottom:5px;font-size:0.9rem}\n'
        '        .ai-section strong{color:var(--text-primary)}\n'
        '        .ai-badge{display:inline-block;background:linear-gradient(135deg,#7c3aed,#2563eb);color:white;font-size:0.7rem;font-weight:700;padding:3px 10px;border-radius:4px;margin-bottom:15px}\n'
        '        .win-strip{display:flex;gap:3px;margin-bottom:20px;flex-wrap:wrap}\n'
        '        .win-block{width:30px;height:30px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:700}\n'
        '        .win-block.W{background:rgba(16,185,129,0.3);color:#10b981} .win-block.L{background:rgba(239,68,68,0.3);color:#ef4444}\n'
        '        .form-card{background:var(--secondary-bg);border:1px solid var(--border-color);border-radius:8px;padding:20px;margin-bottom:20px}\n'
        '        .form-stats{display:flex;gap:30px;flex-wrap:wrap} .form-stat{text-align:center}\n'
        '        .form-stat-label{font-size:0.7rem;color:var(--text-tertiary);text-transform:uppercase}\n'
        '        .form-stat-value{font-family:"Rajdhani",sans-serif;font-size:1.3rem;font-weight:700}\n'
        '        .mh-controls{display:flex;gap:10px;margin-bottom:15px;flex-wrap:wrap;align-items:center}\n'
        '        .mh-search{background:var(--tertiary-bg);border:1px solid var(--border-color);color:var(--text-primary);padding:8px 14px;border-radius:6px;font-size:0.85rem;min-width:200px}\n'
        '        .mh-filter-btn{padding:6px 14px;border:1px solid var(--border-color);background:var(--tertiary-bg);color:var(--text-secondary);border-radius:6px;cursor:pointer;font-size:0.8rem;transition:all 0.2s}\n'
        '        .mh-filter-btn.active{background:var(--accent-red);color:white;border-color:var(--accent-red)}\n'
        '        .mh-row{cursor:pointer;transition:background 0.15s}\n'
        '        .mh-row.win{background:rgba(16,185,129,0.05)} .mh-row.loss{background:rgba(239,68,68,0.05)}\n'
        '        .mh-row:hover{background:rgba(255,255,255,0.05)!important}\n'
        '        .mh-detail{display:none} .mh-detail.open{display:table-row}\n'
        '        .mh-detail td{background:var(--tertiary-bg);padding:15px 20px}\n'
        '        .mh-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}\n'
        '        .mh-detail-stat{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border-color);font-size:0.85rem}\n'
        '        .mh-detail-stat .label{color:var(--text-tertiary)}\n'
        '        .mh-bar{height:20px;border-radius:4px;display:flex;overflow:hidden;margin-top:8px}\n'
        '        .mh-bar-seg{height:100%;display:flex;align-items:center;justify-content:center;font-size:0.6rem;font-weight:700}\n'
        '        .mh-pagination{display:flex;gap:5px;justify-content:center;margin-top:15px}\n'
        '        .mh-page-btn{padding:6px 12px;background:var(--tertiary-bg);border:1px solid var(--border-color);color:var(--text-secondary);border-radius:4px;cursor:pointer;font-size:0.8rem}\n'
        '        .mh-page-btn.active{background:var(--accent-red);color:white;border-color:var(--accent-red)}\n'
        '        .result-W{color:var(--success);font-weight:700} .result-L{color:var(--danger);font-weight:700}\n'
        '    </style>\n'
        '</head>\n'
        '<body>\n'
        '    <header><div class="header-inner"><div><div class="player-name" id="playerName"></div><div class="player-meta" id="playerMeta"></div></div><div class="grade-badge" id="gradeBadge"></div></div></header>\n'
        '    <div class="container">\n'
        '        <div class="tabs">\n'
        '            <button class="tab-btn active" data-tab="overview">Overview</button>\n'
        '            <button class="tab-btn" data-tab="agents">Agents</button>\n'
        '            <button class="tab-btn" data-tab="maps">Maps</button>\n'
        '            <button class="tab-btn" data-tab="trends">Trends</button>\n'
        '            <button class="tab-btn" data-tab="weaknesses">Weaknesses</button>\n'
        '            <button class="tab-btn" data-tab="ai-analysis">AI Analysis</button>\n'
        '            <button class="tab-btn" data-tab="match-history">Match History</button>\n'
        '            <button class="tab-btn" data-tab="resources">Resources</button>\n'
        '        </div>\n'
        '        <div id="overview" class="tab-content active"></div>\n'
        '        <div id="agents" class="tab-content"></div>\n'
        '        <div id="maps" class="tab-content"></div>\n'
        '        <div id="trends" class="tab-content"></div>\n'
        '        <div id="weaknesses" class="tab-content"></div>\n'
        '        <div id="ai-analysis" class="tab-content"></div>\n'
        '        <div id="match-history" class="tab-content"></div>\n'
        '        <div id="resources" class="tab-content"></div>\n'
        '    </div>\n'
        '    <script>\n'
        'const DATA = __DATA_JSON__;\n'
        'const ANALYSIS = __ANALYSIS_JSON__;\n'
        'const AI_HTML = `__AI_ANALYSIS_HTML__`;\n'
        'const player = DATA.player, stats = DATA.stats, allMatches = DATA.all_matches;\n'
        'const recentMatches = DATA.matches, agentStats = DATA.agent_stats, mapStats = DATA.map_stats;\n'
        'const eloHistory = DATA.elo_history, benchmarks = DATA.benchmarks, rankName = DATA.rank_name;\n'
        'const bench = benchmarks[rankName] || benchmarks["Iron"] || {};\n'
        '\n'
        '// Tabs\n'
        'document.querySelectorAll(".tab-btn").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab-btn").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".tab-content").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.getElementById(b.dataset.tab).classList.add("active");}));\n'
        '\n'
        'function wrClass(w){return w>=55?"wr-good":w>=45?"wr-mid":"wr-bad"}\n'
        'function fmtDate(d){if(!d)return"N/A";return new Date(d).toLocaleDateString("en-US",{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}\n'
        '\n'
        '// Header\n'
        'document.getElementById("playerName").textContent=player.name;\n'
        'document.getElementById("playerMeta").innerHTML=[{l:"Rank",v:player.rank},{l:"Peak",v:player.peak_rank},{l:"RR",v:player.rr},{l:"ELO",v:player.elo},{l:"Level",v:player.level},{l:"Region",v:player.region}].map(m=>`<div class="meta-item"><div class="meta-label">${m.l}</div><div class="meta-value">${m.v}</div></div>`).join("");\n'
        'const gb=document.getElementById("gradeBadge");gb.textContent=player.grade;gb.className="grade-badge grade-"+player.grade;\n'
        '\n'
        '// === OVERVIEW ===\n'
        '(function(){\n'
        '  const el=document.getElementById("overview");\n'
        '  const cards=[{l:"K/D",v:stats.kd,b:bench.kd},{l:"HS%",v:stats.hs_pct+"%",b:bench.hs+"%",r:stats.hs_pct,rb:bench.hs},{l:"ADR",v:stats.adr,b:bench.adr},{l:"ACS",v:stats.acs,b:bench.acs},{l:"Win Rate",v:stats.winrate+"%",b:bench.winrate+"%",r:stats.winrate,rb:bench.winrate},{l:"KPR",v:stats.kpr,b:bench.kpr},{l:"DPR",v:stats.dpr,b:bench.dpr,inv:true},{l:"Matches",v:stats.total_matches,b:null},{l:"Rounds",v:stats.total_rounds,b:null}];\n'
        '  let h=\'<div class="stats-grid">\';\n'
        '  cards.forEach(s=>{const rv=s.r!==undefined?s.r:parseFloat(s.v);const rb=s.rb!==undefined?s.rb:parseFloat(s.b);let c="neutral";if(s.b!==null)c=s.inv?(rv<=rb?"good":"bad"):(rv>=rb?"good":"bad");h+=`<div class="stat-card"><div class="stat-label">${s.l}</div><div class="stat-value ${c}">${s.v}</div>${s.b!==null?`<div class="stat-bench">Bench: ${s.b}</div>`:""}</div>`;});\n'
        '  h+=\'</div><div class="chart-box"><div class="chart-title">Performance Radar</div><canvas id="radarChart" width="500" height="400"></canvas></div>\';\n'
        '  el.innerHTML=h;\n'
        '  setTimeout(drawRadar,100);\n'
        '})();\n'
        '\n'
        'function drawRadar(){\n'
        '  const c=document.getElementById("radarChart");if(!c)return;const ctx=c.getContext("2d");\n'
        '  const w=c.width,h=c.height,cx=w/2,cy=h/2,r=Math.min(w,h)*0.35;\n'
        '  const axes=[{l:"K/D",v:stats.kd,b:bench.kd,mx:bench.kd*2},{l:"HS%",v:stats.hs_pct,b:bench.hs,mx:bench.hs*2},{l:"ADR",v:stats.adr,b:bench.adr,mx:bench.adr*1.5},{l:"ACS",v:stats.acs,b:bench.acs,mx:bench.acs*1.5},{l:"KPR",v:stats.kpr,b:bench.kpr,mx:bench.kpr*2},{l:"WR%",v:stats.winrate,b:bench.winrate,mx:100}];\n'
        '  const n=axes.length,step=Math.PI*2/n;\n'
        '  ctx.fillStyle="#0a0e27";ctx.fillRect(0,0,w,h);\n'
        '  for(let ring=0.25;ring<=1;ring+=0.25){ctx.beginPath();for(let i=0;i<=n;i++){const a=-Math.PI/2+i*step;const x=cx+Math.cos(a)*r*ring;const y=cy+Math.sin(a)*r*ring;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}ctx.strokeStyle="rgba(160,169,184,0.15)";ctx.stroke();}\n'
        '  ctx.font="12px Inter";ctx.fillStyle="#a0a9b8";ctx.textAlign="center";\n'
        '  axes.forEach((ax,i)=>{const a=-Math.PI/2+i*step;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx+Math.cos(a)*r,cy+Math.sin(a)*r);ctx.strokeStyle="rgba(160,169,184,0.2)";ctx.stroke();ctx.fillText(ax.l,cx+Math.cos(a)*(r+25),cy+Math.sin(a)*(r+25)+4);});\n'
        '  ctx.beginPath();axes.forEach((ax,i)=>{const a=-Math.PI/2+i*step;const ratio=Math.min(ax.b/ax.mx,1);const x=cx+Math.cos(a)*r*ratio;const y=cy+Math.sin(a)*r*ratio;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});ctx.closePath();ctx.fillStyle="rgba(245,158,11,0.1)";ctx.fill();ctx.strokeStyle="rgba(245,158,11,0.5)";ctx.lineWidth=2;ctx.stroke();\n'
        '  ctx.beginPath();axes.forEach((ax,i)=>{const a=-Math.PI/2+i*step;const ratio=Math.min(ax.v/ax.mx,1);const x=cx+Math.cos(a)*r*ratio;const y=cy+Math.sin(a)*r*ratio;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});ctx.closePath();ctx.fillStyle="rgba(255,70,85,0.2)";ctx.fill();ctx.strokeStyle="#ff4655";ctx.lineWidth=2;ctx.stroke();\n'
        '  axes.forEach((ax,i)=>{const a=-Math.PI/2+i*step;const ratio=Math.min(ax.v/ax.mx,1);ctx.beginPath();ctx.arc(cx+Math.cos(a)*r*ratio,cy+Math.sin(a)*r*ratio,4,0,Math.PI*2);ctx.fillStyle="#ff4655";ctx.fill();});\n'
        '}\n'
        '\n'
        '// === AGENTS ===\n'
        '(function(){const el=document.getElementById("agents");let h=\'<div class="chart-box"><div class="chart-title">Agent Performance</div><canvas id="agentChart" width="800" height="350"></canvas></div><div class="chart-box"><table><thead><tr><th>Agent</th><th>Games</th><th>Win Rate</th><th>K/D</th><th>KPR</th></tr></thead><tbody>\';\n'
        '  agentStats.forEach(a=>{h+=`<tr><td><strong>${a.agent}</strong></td><td>${a.matches}</td><td class="${wrClass(a.winrate)}">${a.winrate}%</td><td>${a.kd}</td><td>${a.kpr}</td></tr>`;});\n'
        '  h+="</tbody></table></div>";el.innerHTML=h;setTimeout(()=>{\n'
        '    const c=document.getElementById("agentChart");if(!c)return;const ctx=c.getContext("2d");const w=c.width,h=c.height;const p={t:20,b:60,l:50,r:20};const top8=agentStats.slice(0,8);\n'
        '    ctx.fillStyle="#1f2937";ctx.fillRect(0,0,w,h);const bw=(w-p.l-p.r)/top8.length*0.7;const gap=(w-p.l-p.r)/top8.length;const mx=Math.max(...top8.map(a=>a.matches));\n'
        '    top8.forEach((a,i)=>{const x=p.l+i*gap+(gap-bw)/2;const bh=(a.matches/mx)*(h-p.t-p.b);const y=h-p.b-bh;ctx.fillStyle=a.winrate>=55?"#10b981":a.winrate>=45?"#f59e0b":"#ef4444";ctx.fillRect(x,y,bw,bh);ctx.fillStyle="#a0a9b8";ctx.font="11px Inter";ctx.textAlign="center";ctx.save();ctx.translate(x+bw/2,h-p.b+15);ctx.rotate(-0.4);ctx.fillText(a.agent,0,0);ctx.restore();ctx.fillStyle="#fff";ctx.font="11px Rajdhani";ctx.fillText(a.matches+"g",x+bw/2,y-5);});\n'
        '  },100);\n'
        '})();\n'
        '\n'
        '// === MAPS ===\n'
        '(function(){const el=document.getElementById("maps");let h=\'<div class="chart-box"><div class="chart-title">Map Win Rates</div><canvas id="mapChart" width="800" height="350"></canvas></div><div class="chart-box"><table><thead><tr><th>Map</th><th>Games</th><th>Win Rate</th></tr></thead><tbody>\';\n'
        '  mapStats.forEach(m=>{h+=`<tr><td><strong>${m.map}</strong></td><td>${m.matches}</td><td class="${wrClass(m.winrate)}">${m.winrate}%</td></tr>`;});\n'
        '  h+="</tbody></table></div>";el.innerHTML=h;setTimeout(()=>{\n'
        '    const c=document.getElementById("mapChart");if(!c)return;const ctx=c.getContext("2d");const w=c.width,h=c.height;const p={t:20,b:60,l:50,r:20};\n'
        '    const sorted=[...mapStats].sort((a,b)=>b.winrate-a.winrate);ctx.fillStyle="#1f2937";ctx.fillRect(0,0,w,h);\n'
        '    const bw=(w-p.l-p.r)/sorted.length*0.7;const gap=(w-p.l-p.r)/sorted.length;\n'
        '    sorted.forEach((m,i)=>{const x=p.l+i*gap+(gap-bw)/2;const bh=(m.winrate/100)*(h-p.t-p.b);const y=h-p.b-bh;ctx.fillStyle=m.winrate>=55?"#10b981":m.winrate>=45?"#f59e0b":"#ef4444";ctx.fillRect(x,y,bw,bh);ctx.fillStyle="#a0a9b8";ctx.font="11px Inter";ctx.textAlign="center";ctx.save();ctx.translate(x+bw/2,h-p.b+15);ctx.rotate(-0.4);ctx.fillText(m.map,0,0);ctx.restore();ctx.fillStyle="#fff";ctx.font="12px Rajdhani";ctx.fillText(m.winrate+"%",x+bw/2,y-5);});\n'
        '    const y50=h-p.b-(50/100)*(h-p.t-p.b);ctx.beginPath();ctx.moveTo(p.l,y50);ctx.lineTo(w-p.r,y50);ctx.strokeStyle="rgba(255,206,71,0.5)";ctx.setLineDash([5,5]);ctx.stroke();ctx.setLineDash([]);\n'
        '  },100);\n'
        '})();\n'
        '\n'
        '// === TRENDS ===\n'
        '(function(){const el=document.getElementById("trends");let h=\'<div class="chart-title">Last 20 Matches</div><div class="win-strip">\';\n'
        '  recentMatches.forEach(m=>{const c=m.won?"W":"L";h+=`<div class="win-block ${c}" title="${m.map} - ${m.agent}">${c}</div>`;});\n'
        '  h+=\'</div><div class="form-card"><div class="chart-title">Recent Form (Last 10) vs Overall</div><div class="form-stats">\';\n'
        '  [{l:"WR",r:stats.recent_wr+"%",o:stats.winrate+"%"},{l:"K/D",r:stats.recent_kd,o:stats.kd},{l:"ADR",r:stats.recent_adr,o:stats.adr},{l:"ACS",r:stats.recent_acs,o:stats.acs}].forEach(s=>{h+=`<div class="form-stat"><div class="form-stat-label">${s.l}</div><div class="form-stat-value">${s.r}</div><div style="font-size:0.7rem;color:var(--text-tertiary)">Overall: ${s.o}</div></div>`;});\n'
        '  h+=\'</div></div><div class="two-col"><div class="chart-box"><div class="chart-title">K/D Trend</div><canvas id="kdTrend" width="400" height="250"></canvas></div><div class="chart-box"><div class="chart-title">ADR Trend</div><canvas id="adrTrend" width="400" height="250"></canvas></div></div>\';\n'
        '  if(eloHistory.length>0)h+=\'<div class="chart-box"><div class="chart-title">ELO Progression</div><canvas id="eloChart" width="800" height="300"></canvas></div>\';\n'
        '  el.innerHTML=h;\n'
        '  setTimeout(()=>{drawLine("kdTrend",recentMatches.map(m=>m.kd).reverse(),"#ff4655");drawLine("adrTrend",recentMatches.map(m=>m.adr).reverse(),"#00e5a0");if(eloHistory.length>0)drawLine("eloChart",eloHistory.map(e=>e.elo),"#ffce47");},100);\n'
        '})();\n'
        '\n'
        'function drawLine(id,vals,color){\n'
        '  const c=document.getElementById(id);if(!c||vals.length===0)return;const ctx=c.getContext("2d");\n'
        '  const w=c.width,h=c.height,p={t:25,b:30,l:50,r:20},cw=w-p.l-p.r,ch=h-p.t-p.b;\n'
        '  ctx.fillStyle="#1f2937";ctx.fillRect(0,0,w,h);\n'
        '  const mn=Math.min(...vals)*0.95,mx=Math.max(...vals)*1.05,rng=mx-mn||1;\n'
        '  ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;\n'
        '  vals.forEach((v,i)=>{const x=p.l+(i/(vals.length-1||1))*cw;const y=p.t+ch-((v-mn)/rng)*ch;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});ctx.stroke();\n'
        '  ctx.fillStyle=color;vals.forEach((v,i)=>{const x=p.l+(i/(vals.length-1||1))*cw;const y=p.t+ch-((v-mn)/rng)*ch;ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();});\n'
        '  ctx.fillStyle="#6b7280";ctx.font="10px Inter";ctx.textAlign="right";\n'
        '  for(let i=0;i<=4;i++){const v=mn+(rng*i/4);const y=p.t+ch-(i/4)*ch;ctx.fillText(v.toFixed(vals[0]>100?0:2),p.l-5,y+3);}\n'
        '}\n'
        '\n'
        '// === WEAKNESSES ===\n'
        '(function(){const el=document.getElementById("weaknesses");if(!ANALYSIS.weaknesses.length){el.innerHTML=\'<div class="chart-box"><p>No significant weaknesses. Great job!</p></div>\';return;}\n'
        '  let h="";ANALYSIS.weaknesses.forEach(w=>{h+=`<div class="weakness-card ${w.severity}"><div class="weakness-header"><div class="weakness-title">${w.title}</div><span class="severity-badge severity-${w.severity}">${w.severity}</span></div><div class="weakness-desc">${w.description}</div><div style="color:var(--text-tertiary);font-size:0.8rem;margin-bottom:6px">Stat: ${w.metric}</div><div class="weakness-drill">${w.drill}</div></div>`;});\n'
        '  el.innerHTML=h;\n'
        '})();\n'
        '\n'
        '// === AI ANALYSIS ===\n'
        '(function(){const el=document.getElementById("ai-analysis");el.innerHTML=\'<div class="ai-badge">Powered by AI (OpenRouter)</div><div class="ai-section">\'+AI_HTML+"</div>";})();\n'
        '\n'
        '// === MATCH HISTORY ===\n'
        '(function(){\n'
        '  const el=document.getElementById("match-history");const PP=20;let page=1,filter="all",search="";\n'
        '  function getF(){let f=allMatches;if(filter==="wins")f=f.filter(m=>m.won);if(filter==="losses")f=f.filter(m=>!m.won);if(search){const q=search.toLowerCase();f=f.filter(m=>m.agent.toLowerCase().includes(q)||m.map.toLowerCase().includes(q)||(m.won?"win":"loss").includes(q));}return f;}\n'
        '  function render(){\n'
        '    const f=getF(),tp=Math.ceil(f.length/PP),st=(page-1)*PP,pg=f.slice(st,st+PP);\n'
        '    let h=\'<div class="mh-controls"><input type="text" class="mh-search" placeholder="Search agent, map, win/loss..." id="mhS">\';\n'
        '    h+=\'<button class="mh-filter-btn\'+(filter==="all"?" active":"")+\'" data-f="all">All</button>\';\n'
        '    h+=\'<button class="mh-filter-btn\'+(filter==="wins"?" active":"")+\'" data-f="wins">Wins</button>\';\n'
        '    h+=\'<button class="mh-filter-btn\'+(filter==="losses"?" active":"")+\'" data-f="losses">Losses</button>\';\n'
        '    h+=`<span style="color:var(--text-tertiary);font-size:0.8rem;margin-left:auto">${f.length} matches</span></div>`;\n'
        '    h+=\'<div class="chart-box" style="overflow-x:auto"><table><thead><tr><th>#</th><th>Date</th><th>Map</th><th>Agent</th><th>Result</th><th>K/D/A</th><th>KD</th><th>HS%</th><th>ADR</th><th>ACS</th><th>Rounds</th></tr></thead><tbody>\';\n'
        '    pg.forEach((m,i)=>{\n'
        '      const idx=st+i+1,cls=m.won?"win":"loss",res=m.won?"W":"L";\n'
        '      h+=`<tr class="mh-row ${cls}" data-idx="${st+i}"><td>${idx}</td><td>${fmtDate(m.date)}</td><td>${m.map}</td><td>${m.agent}</td><td class="result-${res}">${res}</td><td>${m.kills}/${m.deaths}/${m.assists}</td><td class="${m.kd>=bench.kd?"good":"bad"}">${m.kd}</td><td>${m.hs_pct}%</td><td>${m.adr}</td><td>${m.acs}</td><td>${m.rounds}</td></tr>`;\n'
        '      const ts=m.headshots+m.bodyshots+m.legshots||1;\n'
        '      const hp=((m.headshots/ts)*100).toFixed(1),bp=((m.bodyshots/ts)*100).toFixed(1),lp=((m.legshots/ts)*100).toFixed(1);\n'
        '      let mg=0;if(m.kd>=bench.kd)mg+=2;else if(m.kd>=bench.kd*0.85)mg+=1;if(m.hs_pct>=bench.hs)mg+=2;else if(m.hs_pct>=bench.hs*0.85)mg+=1;if(m.adr>=bench.adr)mg+=2;else if(m.adr>=bench.adr*0.85)mg+=1;if(m.acs>=bench.acs)mg+=2;else if(m.acs>=bench.acs*0.85)mg+=1;\n'
        '      const gr=mg>=7?"S":mg>=5?"A":mg>=4?"B":mg>=2?"C":mg>=1?"D":"F";\n'
        '      h+=`<tr class="mh-detail" data-d="${st+i}"><td colspan="11"><div class="mh-detail-grid"><div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">Damage Dealt</span><span>${m.dmg_dealt}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">Damage Received</span><span>${m.dmg_recv}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">Score</span><span>${m.score}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">Rank at Time</span><span>${m.tier_name}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">KPR</span><span>${m.kpr}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">DPR</span><span>${m.dpr}</span></div>`;\n'
        '      h+=`<div class="mh-detail-stat"><span class="label">APR</span><span>${m.apr}</span></div>`;\n'
        '      h+=`</div><div><div style="font-size:0.8rem;color:var(--text-tertiary);margin-bottom:5px">Shot Distribution</div>`;\n'
        '      h+=`<div class="mh-bar"><div class="mh-bar-seg" style="width:${hp}%;background:#10b981">HS ${hp}%</div><div class="mh-bar-seg" style="width:${bp}%;background:#3b82f6">Body ${bp}%</div><div class="mh-bar-seg" style="width:${lp}%;background:#ef4444">Leg ${lp}%</div></div>`;\n'
        '      h+=`<div style="margin-top:15px;font-size:0.8rem;color:var(--text-tertiary)">Match Grade</div><div class="grade-badge grade-${gr}" style="font-size:1.5rem;width:40px;height:40px;margin-top:5px">${gr}</div>`;\n'
        '      h+=`</div></div></td></tr>`;\n'
        '    });\n'
        '    h+="</tbody></table></div>";\n'
        '    if(tp>1){h+=\'<div class="mh-pagination">\';for(let p=1;p<=tp;p++)h+=`<button class="mh-page-btn${p===page?" active":""}" data-p="${p}">${p}</button>`;h+="</div>";}\n'
        '    el.innerHTML=h;\n'
        '    document.getElementById("mhS").value=search;\n'
        '    document.getElementById("mhS").addEventListener("input",e=>{search=e.target.value;page=1;render();});\n'
        '    document.querySelectorAll(".mh-filter-btn").forEach(b=>b.addEventListener("click",()=>{filter=b.dataset.f;page=1;render();}));\n'
        '    document.querySelectorAll(".mh-row").forEach(r=>r.addEventListener("click",()=>{const d=document.querySelector(`[data-d="${r.dataset.idx}"]`);if(d)d.classList.toggle("open");}));\n'
        '    document.querySelectorAll(".mh-page-btn").forEach(b=>b.addEventListener("click",()=>{page=parseInt(b.dataset.p);render();}));\n'
        '  }\n'
        '  render();\n'
        '})();\n'
        '\n'
        '// === RESOURCES ===\n'
        '(function(){const el=document.getElementById("resources");let h="";ANALYSIS.resources.forEach(r=>{h+=`<div class="resource-card"><a href="${r.url}" target="_blank">${r.title}</a><div style="color:var(--text-tertiary);font-size:0.8rem;margin-top:4px">${r.type}</div></div>`;});el.innerHTML=h;})();\n'
        '    </script>\n'
        '</body>\n'
        '</html>'
    )


# ============ MAIN ============
def main():
    parser = argparse.ArgumentParser(description='Valorant Performance Analyzer v2.0')
    parser.add_argument('--name', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--region', required=True, choices=['ap', 'na', 'eu', 'kr'])
    parser.add_argument('--apikey', required=True, help='Henrik API key')
    parser.add_argument('--openrouter-key', required=True, help='OpenRouter API key')
    parser.add_argument('--model', default='google/gemini-2.5-flash')
    args = parser.parse_args()

    print(f"\n=== Valorant Performance Analyzer v2.0 ===")
    print(f"Player: {args.name}#{args.tag} | Region: {args.region}\n")

    api = HenrikAPI(args.apikey)

    account = fetch_account(api, args.name, args.tag)
    if not account:
        print("ERROR: Could not fetch account. Check name/tag."); return

    puuid = account.get('puuid')
    mmr = fetch_mmr(api, args.region, args.name, args.tag)
    mmr_history = fetch_mmr_history(api, args.region, args.name, args.tag)
    raw_matches = fetch_all_matches(api, args.region, args.name, args.tag)
    if not raw_matches:
        print("ERROR: No matches found."); return

    matches = process_all_matches(raw_matches, puuid)
    if not matches:
        print("ERROR: Could not process matches."); return

    stats = calculate_stats(matches)
    current_mmr = mmr.get('current_data', {}) if mmr else {}
    rank_str = current_mmr.get('currenttierpatched', 'Unranked')
    peak_str = (mmr.get('highest_rank', {}) if mmr else {}).get('patched_tier', 'Unknown')
    rank_name = get_rank_name(rank_str)
    benchmarks = RANK_BENCHMARKS.get(rank_name, RANK_BENCHMARKS['Iron'])
    grade = calculate_grade(stats, benchmarks)

    print("\nAnalyzing performance...")
    weaknesses = analyze_weaknesses(stats, benchmarks, rank_name)
    tips = generate_tips(stats, weaknesses, rank_name)
    resources = generate_resources(weaknesses, rank_name)

    ai_text = get_ai_analysis(args.openrouter_key, args.model, stats, matches, rank_str, peak_str, mmr_history)
    ai_html = format_ai_html(ai_text) if ai_text else '<p style="color:var(--text-tertiary);">AI analysis unavailable. See Weaknesses tab for rule-based analysis.</p>'

    print("\nGenerating HTML report...")
    html = generate_html(args.name, args.tag, args.region, account, mmr, mmr_history, matches, stats, weaknesses, tips, resources, ai_html, benchmarks, rank_name, grade)

    output_file = f"{args.name}_{args.tag}_analysis.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n=== Complete ===")
    print(f"Report: {output_file}")
    print(f"  Matches: {stats['total_matches']} | W/L: {stats['wins']}/{stats['losses']} ({stats['winrate']}%)")
    print(f"  K/D: {stats['kd']} | HS%: {stats['hs_pct']}% | ADR: {stats['adr']} | ACS: {stats['acs']}")
    print(f"  Grade: {grade} | Rank: {rank_str}")
    print(f"  Weaknesses: {len(weaknesses)} | AI: {'Yes' if ai_text else 'Fallback'}")


if __name__ == '__main__':
    main()
