#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║        FANTASY SPORTS LEAGUE PREDICTOR                  ║
║        Powered by TheSportsDB Free API                  ║
╚══════════════════════════════════════════════════════════╝

Predicts match outcomes and scores using:
  - Head-to-head history
  - Recent team form
  - Home/away advantage
  - Goal-scoring trends
  - Points-based fantasy scoring

Usage:
  python fantasy_predictor.py
"""

import urllib.request
import urllib.parse
import json
import os
import sys
import time
import random
from datetime import datetime, timedelta
from collections import defaultdict

# ─── ANSI COLOUR PALETTE ─────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    # Greens / teals
    GREEN   = "\033[92m"
    TEAL    = "\033[96m"
    # Accents
    GOLD    = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    GREY    = "\033[90m"
    BG_DARK = "\033[40m"

# ─── API WRAPPER ──────────────────────────────────────────────────────────────
BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"

def api_get(endpoint: str, params: dict = None) -> dict | None:
    """Fetch JSON from TheSportsDB free API (v3, no key needed)."""
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FantasyPredictor/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"{C.RED}  ✗ API error: {e}{C.RESET}")
        return None

# ─── DISPLAY HELPERS ─────────────────────────────────────────────────────────
WIDTH = 62

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n{C.BOLD}{C.TEAL}{'═' * WIDTH}")
    print(f"  ⚽  FANTASY SPORTS LEAGUE PREDICTOR".center(WIDTH))
    print(f"     Powered by TheSportsDB Free API".center(WIDTH))
    print(f"{'═' * WIDTH}{C.RESET}\n")

def section(title: str):
    print(f"\n{C.GOLD}{C.BOLD}  ▸ {title}{C.RESET}")
    print(f"{C.DIM}  {'─' * (WIDTH - 4)}{C.RESET}")

def loading(msg: str, steps: int = 8):
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧"
    for i in range(steps):
        print(f"\r{C.TEAL}  {chars[i % len(chars)]}  {msg}...{C.RESET}", end="", flush=True)
        time.sleep(0.07)
    print(f"\r{C.GREEN}  ✓  {msg}{C.RESET}       ")

def bar(value: float, max_val: float = 100, width: int = 20, colour: str = C.GREEN) -> str:
    filled = int((value / max_val) * width) if max_val else 0
    return f"{colour}{'█' * filled}{C.DIM}{'░' * (width - filled)}{C.RESET}"

# ─── SEARCH & SELECT ─────────────────────────────────────────────────────────
def search_league(query: str) -> dict | None:
    data = api_get("search_all_leagues.php", {"c": query})
    if not data or not data.get("countrys"):
        # Try sport-based search
        data = api_get("all_leagues.php")
        if not data or not data.get("leagues"):
            return None
        matches = [l for l in data["leagues"]
                   if query.lower() in l.get("strLeague", "").lower()
                   or query.lower() in l.get("strSport", "").lower()]
        return matches[:10] if matches else None
    return data.get("countrys", [])[:10]

def search_team(query: str) -> list:
    data = api_get("searchteams.php", {"t": query})
    return data.get("teams", []) if data else []

def pick_from_list(items: list, key_name: str, id_key: str, title: str) -> dict | None:
    if not items:
        print(f"{C.RED}  No results found.{C.RESET}")
        return None
    section(title)
    for i, item in enumerate(items[:10], 1):
        sport = item.get("strSport", "")
        country = item.get("strCountry", "")
        extra = f" {C.DIM}({sport}{', ' + country if country else ''}){C.RESET}" if (sport or country) else ""
        print(f"  {C.GOLD}[{i:2}]{C.RESET} {item.get(key_name, 'Unknown')}{extra}")
    print(f"\n  {C.GREY}[0]  Cancel{C.RESET}")
    while True:
        try:
            choice = int(input(f"\n{C.TEAL}  Choose ▸ {C.RESET}").strip())
            if choice == 0:
                return None
            if 1 <= choice <= len(items[:10]):
                return items[choice - 1]
        except ValueError:
            pass
        print(f"{C.RED}  Invalid choice.{C.RESET}")

# ─── DATA FETCHERS ────────────────────────────────────────────────────────────
def get_team_last_events(team_id: str, n: int = 15) -> list:
    data = api_get("eventslast.php", {"id": team_id})
    events = data.get("results", []) if data else []
    return events[:n]

def get_team_next_events(team_id: str, n: int = 5) -> list:
    data = api_get("eventsnext.php", {"id": team_id})
    return (data.get("events", []) if data else [])[:n]

def get_h2h(team1_id: str, team2_id: str) -> list:
    data = api_get("eventsh2h.php", {"idHomeTeam": team1_id, "idAwayTeam": team2_id})
    return data.get("results", []) if data else []

def get_league_table(league_id: str, season: str = None) -> list:
    if not season:
        season = _current_season()
    data = api_get("lookuptable.php", {"l": league_id, "s": season})
    return data.get("table", []) if data else []

def get_team_details(team_id: str) -> dict | None:
    data = api_get("lookupteam.php", {"id": team_id})
    teams = data.get("teams", []) if data else []
    return teams[0] if teams else None

def _current_season() -> str:
    now = datetime.utcnow()
    y = now.year
    return f"{y - 1}-{y}" if now.month < 8 else f"{y}-{y + 1}"

# ─── PREDICTION ENGINE ────────────────────────────────────────────────────────
class PredictionEngine:
    """
    Lightweight prediction model using:
      1. Head-to-head win rate
      2. Recent form (last 10 matches, exponential weight)
      3. Home advantage factor
      4. Average goals scored/conceded
      5. League position (if available)
    """

    FORM_WEIGHTS = [0.25, 0.20, 0.15, 0.12, 0.10, 0.07, 0.04, 0.03, 0.02, 0.02]

    def _parse_score(self, event: dict, team_id: str) -> tuple[int, int] | None:
        """Return (goals_for, goals_against) for team_id in this event."""
        hid = str(event.get("idHomeTeam", ""))
        aid = str(event.get("idAwayTeam", ""))
        hs  = event.get("intHomeScore")
        as_ = event.get("intAwayScore")
        if hs is None or as_ is None:
            return None
        try:
            hs, as_ = int(hs), int(as_)
        except (TypeError, ValueError):
            return None
        if hid == str(team_id):
            return hs, as_
        if aid == str(team_id):
            return as_, hs
        return None

    def _result(self, gf: int, ga: int) -> str:
        if gf > ga: return "W"
        if gf < ga: return "L"
        return "D"

    def _form_score(self, events: list, team_id: str) -> float:
        """Weighted form score 0-1 from recent events (most recent first)."""
        scores = []
        for ev in events:
            parsed = self._parse_score(ev, team_id)
            if parsed:
                r = self._result(*parsed)
                scores.append(1.0 if r == "W" else 0.5 if r == "D" else 0.0)
        total, wsum = 0.0, 0.0
        for i, s in enumerate(scores[:10]):
            w = self.FORM_WEIGHTS[i]
            total += s * w
            wsum  += w
        return total / wsum if wsum else 0.5

    def _avg_goals(self, events: list, team_id: str) -> tuple[float, float]:
        gf_list, ga_list = [], []
        for ev in events:
            parsed = self._parse_score(ev, team_id)
            if parsed:
                gf_list.append(parsed[0])
                ga_list.append(parsed[1])
        if not gf_list:
            return 1.2, 1.2
        return sum(gf_list) / len(gf_list), sum(ga_list) / len(ga_list)

    def _h2h_advantage(self, h2h: list, home_id: str, away_id: str) -> float:
        """Returns win-rate for home_id in h2h (0-1)."""
        hw = aw = d = 0
        for ev in h2h:
            hid = str(ev.get("idHomeTeam", ""))
            aid = str(ev.get("idAwayTeam", ""))
            hs  = ev.get("intHomeScore")
            as_ = ev.get("intAwayScore")
            if hs is None or as_ is None:
                continue
            try:
                hs, as_ = int(hs), int(as_)
            except (TypeError, ValueError):
                continue
            if str(home_id) in (hid, aid) and str(away_id) in (hid, aid):
                gf = hs if hid == str(home_id) else as_
                ga = as_ if hid == str(home_id) else hs
                r  = self._result(gf, ga)
                if r == "W": hw += 1
                elif r == "L": aw += 1
                else: d += 1
        total = hw + aw + d
        if total == 0:
            return 0.5
        return (hw + 0.5 * d) / total

    def predict(
        self,
        home_team: dict,
        away_team: dict,
        home_events: list,
        away_events: list,
        h2h: list,
        home_table_row: dict | None = None,
        away_table_row: dict | None = None,
    ) -> dict:
        hid = home_team["idTeam"]
        aid = away_team["idTeam"]

        # 1. Form scores
        h_form = self._form_score(home_events, hid)
        a_form = self._form_score(away_events, aid)

        # 2. Average goals
        h_atk, h_def = self._avg_goals(home_events, hid)
        a_atk, a_def = self._avg_goals(away_events, aid)

        # 3. H2H
        h2h_factor = self._h2h_advantage(h2h, hid, aid)

        # 4. Home advantage (typically ~0.3 goal boost)
        home_boost = 0.15

        # 5. League position influence
        h_pos_factor = a_pos_factor = 0.5
        if home_table_row and away_table_row:
            try:
                hp = int(home_table_row.get("intRank", 10))
                ap = int(away_table_row.get("intRank", 10))
                max_pos = max(hp, ap, 20)
                h_pos_factor = 1 - (hp / max_pos)
                a_pos_factor = 1 - (ap / max_pos)
            except (ValueError, TypeError):
                pass

        # Composite strength score (0-1)
        h_str = (h_form * 0.40 + h2h_factor * 0.25 + h_pos_factor * 0.20 + home_boost * 0.15)
        a_str = (a_form * 0.40 + (1 - h2h_factor) * 0.25 + a_pos_factor * 0.20)

        total = h_str + a_str or 1.0
        h_win_prob = h_str / total
        a_win_prob = a_str / total

        # Draw probability: highest when strengths are close
        diff = abs(h_str - a_str)
        draw_prob = max(0.10, 0.32 - diff * 1.5)
        scale = 1 - draw_prob
        h_win_prob *= scale
        a_win_prob *= scale

        # Predicted goals (Poisson-like expected value)
        h_xg = round((h_atk + a_def) / 2 * (1 + home_boost), 2)
        a_xg = round((a_atk + h_def) / 2, 2)

        # Likely scoreline: round to nearest integer
        h_score = max(0, round(h_xg + random.gauss(0, 0.3)))
        a_score = max(0, round(a_xg + random.gauss(0, 0.3)))

        # Fantasy points estimate
        def fantasy_pts(goals: int, conceded: int, win: bool, draw: bool) -> int:
            pts = goals * 4
            if conceded == 0: pts += 4
            if win: pts += 6
            if draw: pts += 3
            pts -= conceded * 1
            return max(0, pts)

        home_win = h_score > a_score
        draw     = h_score == a_score
        h_fpts   = fantasy_pts(h_score, a_score, home_win, draw)
        a_fpts   = fantasy_pts(a_score, h_score, not home_win and not draw, draw)

        return {
            "home_win_prob"  : round(h_win_prob * 100, 1),
            "away_win_prob"  : round(a_win_prob * 100, 1),
            "draw_prob"      : round(draw_prob * 100, 1),
            "home_xg"        : h_xg,
            "away_xg"        : a_xg,
            "pred_home_score": h_score,
            "pred_away_score": a_score,
            "home_form"      : round(h_form * 100, 1),
            "away_form"      : round(a_form * 100, 1),
            "h2h_home_rate"  : round(h2h_factor * 100, 1),
            "home_fantasy_pts": h_fpts,
            "away_fantasy_pts": a_fpts,
            "home_atk"       : round(h_atk, 2),
            "away_atk"       : round(a_atk, 2),
        }

# ─── DISPLAY RESULTS ─────────────────────────────────────────────────────────
def display_prediction(home: dict, away: dict, pred: dict, h2h: list):
    h_name = home.get("strTeam", "Home")
    a_name = away.get("strTeam", "Away")

    section("MATCH PREDICTION")
    print(f"\n  {C.BOLD}{C.WHITE}{h_name:>26}  vs  {a_name}{C.RESET}")
    print()

    # Scoreline
    hs = pred["pred_home_score"]
    as_ = pred["pred_away_score"]
    score_str = f"  {C.BOLD}{C.GOLD}Predicted Score:  {h_name} {hs} – {as_} {a_name}{C.RESET}"
    print(score_str)
    print()

    # Win probabilities
    print(f"  {'Win Probability':20}  {h_name[:18]:>18}   {a_name[:18]}")
    hc = C.GREEN if pred["home_win_prob"] > pred["away_win_prob"] else C.DIM
    ac = C.GREEN if pred["away_win_prob"] > pred["home_win_prob"] else C.DIM
    print(f"  {bar(pred['home_win_prob'], 100, 14, hc)} {C.GOLD}{pred['home_win_prob']:5.1f}%{C.RESET}  "
          f"  Draw {C.TEAL}{pred['draw_prob']:4.1f}%{C.RESET}  "
          f"{C.GOLD}{pred['away_win_prob']:5.1f}%{C.RESET} {bar(pred['away_win_prob'], 100, 14, ac)}")
    print()

    # Expected goals
    section("EXPECTED GOALS (xG)")
    print(f"  {h_name[:22]:22}  xG: {C.TEAL}{pred['home_xg']:.2f}{C.RESET}  {bar(pred['home_xg'], 4, 16, C.TEAL)}")
    print(f"  {a_name[:22]:22}  xG: {C.TEAL}{pred['away_xg']:.2f}{C.RESET}  {bar(pred['away_xg'], 4, 16, C.TEAL)}")

    # Form
    section("RECENT FORM (weighted)")
    print(f"  {h_name[:22]:22}  {bar(pred['home_form'], 100, 16, C.GREEN)}  {C.GOLD}{pred['home_form']:5.1f}%{C.RESET}")
    print(f"  {a_name[:22]:22}  {bar(pred['away_form'], 100, 16, C.GREEN)}  {C.GOLD}{pred['away_form']:5.1f}%{C.RESET}")

    # H2H
    section(f"HEAD-TO-HEAD  ({len(h2h)} recorded matches)")
    print(f"  {h_name} H2H win rate: {C.GOLD}{pred['h2h_home_rate']:.1f}%{C.RESET}  "
          f"{bar(pred['h2h_home_rate'], 100, 20, C.BLUE)}")

    # Attack strength
    section("AVG GOALS SCORED (last 15 matches)")
    print(f"  {h_name[:22]:22}  {C.MAGENTA}{pred['home_atk']:.2f}{C.RESET} goals/match")
    print(f"  {a_name[:22]:22}  {C.MAGENTA}{pred['away_atk']:.2f}{C.RESET} goals/match")

    # Fantasy points
    section("FANTASY POINTS ESTIMATE")
    hf = pred["home_fantasy_pts"]
    af = pred["away_fantasy_pts"]
    print(f"  {h_name[:22]:22}  {C.GOLD}{hf:3d} pts{C.RESET}  {bar(hf, max(hf, af, 20), 16, C.GOLD)}")
    print(f"  {a_name[:22]:22}  {C.GOLD}{af:3d} pts{C.RESET}  {bar(af, max(hf, af, 20), 16, C.GOLD)}")

    # Verdict
    section("VERDICT")
    if pred["home_win_prob"] > pred["away_win_prob"] + 10:
        verdict = f"🏠  {C.GREEN}{h_name} to WIN{C.RESET}"
    elif pred["away_win_prob"] > pred["home_win_prob"] + 10:
        verdict = f"✈️   {C.GREEN}{a_name} to WIN{C.RESET}"
    else:
        verdict = f"⚖️   {C.TEAL}Too close to call — leaning DRAW{C.RESET}"
    print(f"  {verdict}")
    print(f"\n  {C.DIM}* Predictions are probabilistic estimates, not guarantees.{C.RESET}")
    print(f"{C.DIM}{'─' * WIDTH}{C.RESET}")

def display_recent_form(events: list, team_id: str, team_name: str):
    section(f"LAST {min(len(events), 10)} RESULTS — {team_name.upper()}")
    shown = 0
    for ev in events:
        if shown >= 10:
            break
        hs  = ev.get("intHomeScore")
        as_ = ev.get("intAwayScore")
        if hs is None or as_ is None:
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (ValueError, TypeError):
            continue
        hid = str(ev.get("idHomeTeam", ""))
        at_home = hid == str(team_id)
        gf = hs if at_home else as_
        ga = as_ if at_home else hs
        result = "W" if gf > ga else ("D" if gf == ga else "L")
        rc = C.GREEN if result == "W" else (C.GOLD if result == "D" else C.RED)
        venue = "🏠" if at_home else "✈️ "
        date  = ev.get("dateEvent", "")[:10]
        opp   = ev.get("strAwayTeam" if at_home else "strHomeTeam", "Unknown")[:20]
        print(f"  {venue} {date}  {rc}{C.BOLD}{result}{C.RESET}  {gf}–{ga}  vs {opp}")
        shown += 1

def display_league_table(table: list, highlight_ids: list):
    if not table:
        print(f"  {C.DIM}No table data available.{C.RESET}")
        return
    section("LEAGUE TABLE (TOP 10)")
    print(f"  {C.DIM}{'Pos':>3}  {'Team':<22} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GD':>4} {'Pts':>4}{C.RESET}")
    for row in table[:10]:
        pos  = row.get("intRank", "-")
        name = row.get("strTeam", "")[:22]
        p    = row.get("intPlayed", "-")
        w    = row.get("intWin", "-")
        d    = row.get("intDraw", "-")
        l    = row.get("intLoss", "-")
        gd   = row.get("intGoalDifference", "-")
        pts  = row.get("intPoints", "-")
        tid  = str(row.get("idTeam", ""))
        hl   = tid in [str(x) for x in highlight_ids]
        colour = C.GOLD + C.BOLD if hl else ""
        reset  = C.RESET if hl else ""
        marker = " ◄" if hl else ""
        print(f"  {colour}{pos:>3}  {name:<22} {p:>3} {w:>3} {d:>3} {l:>3} {gd:>4} {pts:>4}{marker}{reset}")

# ─── MAIN FLOW ────────────────────────────────────────────────────────────────
def run_predictor():
    engine = PredictionEngine()

    while True:
        banner()
        print(f"  {C.WHITE}Welcome to the Fantasy Sports League Predictor!{C.RESET}")
        print(f"  {C.DIM}Get AI-powered match predictions and fantasy scores.{C.RESET}\n")

        print(f"  {C.GOLD}[1]{C.RESET}  Predict a specific match (search two teams)")
        print(f"  {C.GOLD}[2]{C.RESET}  Browse upcoming fixtures for a team")
        print(f"  {C.GOLD}[3]{C.RESET}  View league table + form")
        print(f"  {C.GOLD}[0]{C.RESET}  Quit\n")

        choice = input(f"{C.TEAL}  Choose ▸ {C.RESET}").strip()

        if choice == "0":
            print(f"\n{C.TEAL}  Thanks for using Fantasy Predictor. Good luck! 🏆{C.RESET}\n")
            break

        elif choice == "1":
            _mode_predict(engine)

        elif choice == "2":
            _mode_fixtures()

        elif choice == "3":
            _mode_league_table()

        else:
            print(f"{C.RED}  Invalid choice.{C.RESET}")

        input(f"\n{C.DIM}  Press Enter to return to menu...{C.RESET}")


def _mode_predict(engine: PredictionEngine):
    banner()
    section("PREDICT A MATCH")

    # Search home team
    print(f"\n  {C.WHITE}Step 1 — Home Team{C.RESET}")
    q = input(f"{C.TEAL}  Search team name ▸ {C.RESET}").strip()
    if not q:
        return
    loading("Searching teams")
    results = search_team(q)
    home_team = pick_from_list(results, "strTeam", "idTeam", "Select Home Team")
    if not home_team:
        return

    # Search away team
    print(f"\n  {C.WHITE}Step 2 — Away Team{C.RESET}")
    q = input(f"{C.TEAL}  Search team name ▸ {C.RESET}").strip()
    if not q:
        return
    loading("Searching teams")
    results = search_team(q)
    away_team = pick_from_list(results, "strTeam", "idTeam", "Select Away Team")
    if not away_team:
        return

    hid = home_team["idTeam"]
    aid = away_team["idTeam"]

    loading("Fetching home team form")
    home_events = get_team_last_events(hid, 15)

    loading("Fetching away team form")
    away_events = get_team_last_events(aid, 15)

    loading("Fetching head-to-head history")
    h2h = get_h2h(hid, aid)

    loading("Running prediction model")
    pred = engine.predict(home_team, away_team, home_events, away_events, h2h)

    banner()
    display_recent_form(home_events, hid, home_team.get("strTeam", "Home"))
    display_recent_form(away_events, aid, away_team.get("strTeam", "Away"))
    display_prediction(home_team, away_team, pred, h2h)


def _mode_fixtures():
    banner()
    section("UPCOMING FIXTURES")

    q = input(f"{C.TEAL}  Search team name ▸ {C.RESET}").strip()
    if not q:
        return
    loading("Searching teams")
    results = search_team(q)
    team = pick_from_list(results, "strTeam", "idTeam", "Select Team")
    if not team:
        return

    loading("Fetching upcoming fixtures")
    fixtures = get_team_next_events(team["idTeam"], 5)

    section(f"NEXT FIXTURES — {team.get('strTeam', '').upper()}")
    if not fixtures:
        print(f"  {C.DIM}No upcoming fixtures found.{C.RESET}")
        return

    for i, ev in enumerate(fixtures, 1):
        date    = ev.get("dateEvent", "TBD")
        home    = ev.get("strHomeTeam", "?")
        away    = ev.get("strAwayTeam", "?")
        league  = ev.get("strLeague", "")
        time_   = ev.get("strTime", "")[:5] if ev.get("strTime") else ""
        print(f"\n  {C.GOLD}[{i}]{C.RESET}  {C.WHITE}{date}{C.RESET}  {time_}")
        print(f"       {home}  vs  {away}")
        print(f"       {C.DIM}{league}{C.RESET}")

    # Offer to predict any fixture
    print(f"\n  {C.TEAL}Enter a fixture number to predict it, or 0 to skip:{C.RESET}")
    try:
        pick = int(input(f"{C.TEAL}  ▸ {C.RESET}").strip())
        if 1 <= pick <= len(fixtures):
            ev = fixtures[pick - 1]
            hid = ev.get("idHomeTeam")
            aid = ev.get("idAwayTeam")
            if hid and aid:
                loading("Fetching team data")
                # Build minimal team dicts
                home_t = {"idTeam": hid, "strTeam": ev.get("strHomeTeam", "Home")}
                away_t = {"idTeam": aid, "strTeam": ev.get("strAwayTeam", "Away")}
                home_ev = get_team_last_events(hid, 15)
                away_ev = get_team_last_events(aid, 15)
                h2h     = get_h2h(hid, aid)
                engine  = PredictionEngine()
                pred    = engine.predict(home_t, away_t, home_ev, away_ev, h2h)
                banner()
                display_recent_form(home_ev, hid, home_t["strTeam"])
                display_recent_form(away_ev, aid, away_t["strTeam"])
                display_prediction(home_t, away_t, pred, h2h)
    except ValueError:
        pass


def _mode_league_table():
    banner()
    section("LEAGUE TABLE LOOKUP")

    # Common leagues for quick access
    COMMON = [
        {"idLeague": "4328", "strLeague": "English Premier League",    "strSport": "Soccer"},
        {"idLeague": "4335", "strLeague": "Spanish La Liga",            "strSport": "Soccer"},
        {"idLeague": "4331", "strLeague": "Bundesliga",                 "strSport": "Soccer"},
        {"idLeague": "4332", "strLeague": "French Ligue 1",             "strSport": "Soccer"},
        {"idLeague": "4334", "strLeague": "Italian Serie A",            "strSport": "Soccer"},
        {"idLeague": "4480", "strLeague": "NBA",                        "strSport": "Basketball"},
        {"idLeague": "4424", "strLeague": "NHL",                        "strSport": "Ice Hockey"},
        {"idLeague": "4391", "strLeague": "NFL",                        "strSport": "American Football"},
        {"idLeague": "4346", "strLeague": "MLB",                        "strSport": "Baseball"},
    ]

    print(f"\n  {C.DIM}Quick-select a popular league, or enter 0 to search:{C.RESET}")
    for i, l in enumerate(COMMON, 1):
        print(f"  {C.GOLD}[{i:2}]{C.RESET}  {l['strLeague']}  {C.DIM}({l['strSport']}){C.RESET}")
    print(f"  {C.GOLD}[ 0]{C.RESET}  Search by name")

    choice = input(f"\n{C.TEAL}  Choose ▸ {C.RESET}").strip()
    league = None

    if choice == "0":
        q = input(f"{C.TEAL}  Search league ▸ {C.RESET}").strip()
        loading("Searching leagues")
        data = api_get("all_leagues.php")
        all_leagues = data.get("leagues", []) if data else []
        matches = [l for l in all_leagues if q.lower() in l.get("strLeague", "").lower()]
        league = pick_from_list(matches, "strLeague", "idLeague", "Select League")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(COMMON):
                league = COMMON[idx]
        except ValueError:
            pass

    if not league:
        return

    lid    = league.get("idLeague")
    season = _current_season()
    loading(f"Fetching {league.get('strLeague')} table ({season})")
    table  = get_league_table(lid, season)

    banner()
    print(f"\n  {C.BOLD}{C.WHITE}{league.get('strLeague')} — Season {season}{C.RESET}")
    display_league_table(table, [])

    # Optional: pick a team to see their form
    if table:
        print(f"\n  {C.TEAL}Enter position number to see a team's recent form (or 0 to skip):{C.RESET}")
        try:
            pos = int(input(f"{C.TEAL}  ▸ {C.RESET}").strip())
            if 1 <= pos <= len(table):
                row  = table[pos - 1]
                tid  = row.get("idTeam")
                tnam = row.get("strTeam", "Team")
                if tid:
                    loading(f"Fetching {tnam} form")
                    events = get_team_last_events(tid, 10)
                    display_recent_form(events, tid, tnam)
        except ValueError:
            pass


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        run_predictor()
    except KeyboardInterrupt:
        print(f"\n\n{C.TEAL}  Exiting. Good luck with your fantasy league! 🏆{C.RESET}\n")
        sys.exit(0)