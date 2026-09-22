#!/usr/bin/env python3
"""
Custom Animated GitHub Contribution Snake Game Generator
Target User: iamkanhaiyakumar
Repository: iamkanhaiyakumar/iamkanhaiyakumar

Generates a standalone animated SVG based on real GitHub contribution data.
"""

import sys
import os
import argparse
import datetime
import json
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

TARGET_USER = "iamkanhaiyakumar"


def fetch_contributions_graphql(user=TARGET_USER, token=None):
    """
    Tier 1: Queries official GitHub GraphQL API targeting the user explicitly.
    Explicitly requests user(login: "iamkanhaiyakumar"), NEVER viewer.
    """
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("No GITHUB_TOKEN provided for GraphQL fetch.")

    print(f"[*] Querying GitHub GraphQL API for user: '{user}'...")
    url = "https://api.github.com/graphql"
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
                weekday
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": user}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "github-snake-game-generator",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        res = json.loads(resp.read().decode("utf-8"))

    if "errors" in res:
        raise RuntimeError(f"GraphQL returned errors: {res['errors']}")

    user_obj = res.get("data", {}).get("user")
    if not user_obj:
        raise RuntimeError(f"User '{user}' not found in GitHub GraphQL response.")

    cal = user_obj["contributionsCollection"]["contributionCalendar"]
    print(f"[+] GraphQL fetch successful! Total contributions: {cal.get('totalContributions')}")
    return cal


def fetch_contributions_fallback(user=TARGET_USER):
    """
    Tier 2 Fallback: Fetches the public contribution calendar endpoint for the user.
    Parses real dates, weekdays, and counts with zero third-party dependencies.
    """
    print(f"[*] Fetching public contribution calendar endpoint for user: '{user}'...")
    url = f"https://github.com/users/{user}/contributions"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8")

    tds = re.findall(r'<td\s+[^>]*class="[^"]*ContributionCalendar-day[^"]*"[^>]*>', html)
    if not tds:
        raise RuntimeError(
            f"Could not parse contribution days for user '{user}' from public endpoint."
        )

    tooltip_pattern = r'<tool-tip[^>]*for="(?P<id>[^"]+)"[^>]*>(?P<text>[^<]+)</tool-tip>'
    tooltips = dict(re.findall(tooltip_pattern, html))

    parsed_cells = {}
    max_col = 0
    total_contributions = 0

    for td in tds:
        date_m = re.search(r'data-date="([^"]+)"', td)
        id_m = re.search(r'id="contribution-day-component-(\d+)-(\d+)"', td)
        level_m = re.search(r'data-level="(\d+)"', td)

        if date_m and id_m:
            date_str = date_m.group(1)
            row = int(id_m.group(1))  # 0 to 6 (Sunday to Saturday)
            col = int(id_m.group(2))  # 0 to max week column
            level = int(level_m.group(1)) if level_m else 0
            tip = tooltips.get(f"contribution-day-component-{row}-{col}", "")

            count = 0
            cm = re.search(r"(\d+)\s+contribution", tip)
            if cm:
                count = int(cm.group(1))
            elif level > 0:
                count = level

            total_contributions += count
            if col not in parsed_cells:
                parsed_cells[col] = {}
            parsed_cells[col][row] = {
                "date": date_str,
                "contributionCount": count,
                "contributionLevel": level,
                "weekday": row,
            }
            if col > max_col:
                max_col = col

    weeks = []
    for c in range(max_col + 1):
        col_days = []
        for r in range(7):
            if c in parsed_cells and r in parsed_cells[c]:
                col_days.append(parsed_cells[c][r])
        weeks.append({"contributionDays": col_days})

    print(f"[+] Fallback fetch successful! Total weeks: {len(weeks)}, Total contributions: {total_contributions}")
    return {
        "totalContributions": total_contributions,
        "weeks": weeks,
    }


def get_contribution_calendar(user=TARGET_USER, token=None):
    """
    Attempts GraphQL first (if token available), falls back to public endpoint.
    If both fail, raises a clear error. Never generates fake or random data.
    """
    if token or os.environ.get("GITHUB_TOKEN"):
        try:
            return fetch_contributions_graphql(user, token)
        except Exception as e:
            print(f"[!] GraphQL fetch failed: {e}")
            print("[!] Falling back to public endpoint...")

    try:
        return fetch_contributions_fallback(user)
    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve contribution data for user '{user}' from both GraphQL and public endpoints: {e}"
        )


def build_snake_game_svg(cal_data, user=TARGET_USER):
    """
    Builds the custom animated SVG Snake Game using real contribution data.
    Dynamic grid dimensions based on the actual weeks returned.
    """
    weeks = cal_data["weeks"]
    num_weeks = len(weeks)
    total_contributions = cal_data.get("totalContributions", 0)

    all_days = []
    food_days = []
    empty_days = []

    for w_idx, week in enumerate(weeks):
        for day in week["contributionDays"]:
            entry = {
                "col": w_idx,
                "row": day["weekday"],
                "date": day["date"],
                "count": day["contributionCount"],
                "level": day.get("contributionLevel", 0),
            }
            all_days.append(entry)
            if day["contributionCount"] >= 1:
                food_days.append(entry)
            else:
                empty_days.append(entry)

    if not food_days:
        raise ValueError(f"No contribution food days found for user {user}.")

    # Streaks calculation
    all_days_sorted = sorted(all_days, key=lambda x: x["date"])
    curr_streak = 0
    max_streak = 0
    for d in all_days_sorted:
        if d["count"] >= 1:
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
        else:
            curr_streak = 0

    # Food tier configuration
    def get_tier_info(count):
        if count >= 10:
            return 4, "#ff007f", 100  # Special: Neon Magenta (100 pts)
        elif count >= 6:
            return 3, "#ffd700", 50   # Bonus: Gold (50 pts)
        elif count >= 3:
            return 2, "#00f7ff", 25   # Higher-value: Electric Cyan (25 pts)
        else:
            return 1, "#39d353", 10   # Normal: Vibrant Green (10 pts)

    total_score = sum(get_tier_info(d["count"])[2] for d in food_days)

    # Path planning: Snake travels across grid to eat every food cell
    targets = [(d["col"], d["row"]) for d in food_days]
    target_set = set(targets)

    curr = (0, 0)
    unvisited = set(targets)
    path = [curr]

    def get_grid_steps(start, end):
        sc, sr = start
        ec, er = end
        steps = []
        c_step = 1 if ec >= sc else -1
        r_step = 1 if er >= sr else -1
        c = sc
        while c != ec:
            c += c_step
            steps.append((c, sr))
        r = sr
        while r != er:
            r += r_step
            steps.append((ec, r))
        return steps

    while unvisited:
        best = None
        best_dist = 999999
        for t in unvisited:
            dist = abs(t[0] - curr[0]) + abs(t[1] - curr[1])
            if t[0] >= curr[0]:
                dist -= 0.1  # Natural forward progression across calendar
            if dist < best_dist:
                best_dist = dist
                best = t
        steps = get_grid_steps(curr, best)
        path.extend(steps)
        curr = best
        unvisited.remove(best)

    # Smooth return path back to (0, 0)
    return_steps = get_grid_steps(curr, (0, 0))
    path.extend(return_steps)

    total_steps = len(path)
    step_duration = 0.08  # Noticeably fast (80ms per grid cell)
    total_duration = round(total_steps * step_duration, 2)

    # Record first-eaten step for each target
    food_eaten_step = {}
    for step_idx, pos in enumerate(path):
        if pos in target_set and pos not in food_eaten_step:
            food_eaten_step[pos] = step_idx

    # Dynamic layout calculations
    cell_size = 11
    cell_gap = 3
    pitch = cell_size + cell_gap

    margin_left = 34
    margin_top = 65
    margin_right = 20
    margin_bottom = 20

    grid_width = num_weeks * pitch - cell_gap
    grid_height = 7 * pitch - cell_gap

    total_width = margin_left + grid_width + margin_right
    total_height = margin_top + grid_height + margin_bottom

    # Month Labels
    month_labels = []
    months_seen = set()
    for d in all_days_sorted:
        dt = datetime.date.fromisoformat(d["date"])
        if dt.day <= 7 and dt.month not in months_seen:
            months_seen.add(dt.month)
            month_name = dt.strftime("%b")
            x = margin_left + d["col"] * pitch
            month_labels.append((month_name, x))

    # Helper for snake segment coordinate at step
    def get_pos(step_idx):
        pos = path[step_idx % total_steps]
        x = margin_left + pos[0] * pitch + cell_size / 2
        y = margin_top + pos[1] * pitch + cell_size / 2
        return x, y

    # Generate CSS
    css_parts = [
        "/* Custom Animated GitHub Snake Game */",
        f"@keyframes hudProgress {{ 0% {{ width: 0px; }} 100% {{ width: {grid_width}px; }} }}",
    ]

    # Snake head and body keyframes (5 segments)
    num_segments = 5
    for seg in range(num_segments):
        seg_name = "head" if seg == 0 else f"b{seg}"
        kf = [f"@keyframes move_{seg_name} {{"]
        for step_idx in range(total_steps):
            pct = round((step_idx / total_steps) * 100, 2)
            actual_step = (step_idx - seg) % total_steps
            x, y = get_pos(actual_step)
            kf.append(f"  {pct}% {{ transform: translate({x}px, {y}px); }}")
        x0, y0 = get_pos((total_steps - seg) % total_steps)
        kf.append(f"  100% {{ transform: translate({x0}px, {y0}px); }}")
        kf.append("}")
        css_parts.append("\n".join(kf))

    # Food eating keyframes
    for target in targets:
        step_eaten = food_eaten_step.get(target, 0)
        pct_eaten = round((step_eaten / total_steps) * 100, 2)
        tier, color, pts = get_tier_info(
            next(d["count"] for d in food_days if (d["col"], d["row"]) == target)
        )
        c, r = target
        css_parts.append(
            f"""
        @keyframes eat_{c}_{r} {{
          0%, {max(0.0, pct_eaten - 0.2)}% {{
            fill: {color};
            opacity: 1;
            transform: scale(1);
          }}
          {pct_eaten}% {{
            fill: #ffffff;
            opacity: 1;
            transform: scale(1.35);
          }}
          {min(100.0, pct_eaten + 0.5)}%, 100% {{
            fill: #196127;
            opacity: 0.65;
            transform: scale(1);
          }}
        }}"""
        )

    css_text = "\n".join(css_parts)

    # SVG Construction
    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {total_height}" width="100%" height="{total_height}" style="background:#0d1117;border-radius:12px;border:1px solid #30363d;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif;">'
    )
    svg.append('  <defs>')
    svg.append('    <linearGradient id="hudGrad" x1="0%" y1="0%" x2="100%" y2="0%">')
    svg.append('      <stop offset="0%" stop-color="#00f7ff" />')
    svg.append('      <stop offset="50%" stop-color="#39d353" />')
    svg.append('      <stop offset="100%" stop-color="#ffd700" />')
    svg.append('    </linearGradient>')
    svg.append('    <filter id="glow" x="-25%" y="-25%" width="150%" height="150%">')
    svg.append('      <feGaussianBlur stdDeviation="2.5" result="blur" />')
    svg.append('      <feComposite in="SourceGraphic" in2="blur" operator="over" />')
    svg.append('    </filter>')
    svg.append('    <style>')
    svg.append(css_text)
    svg.append(
        f'      .snake-head {{ animation: move_head {total_duration}s linear infinite; filter: url(#glow); }}'
    )
    for s in range(1, num_segments):
        svg.append(
            f'      .snake-b{s} {{ animation: move_b{s} {total_duration}s linear infinite; }}'
        )
    svg.append(
        f'      .hud-prog {{ animation: hudProgress {total_duration}s linear infinite; }}'
    )
    svg.append('    </style>')
    svg.append('  </defs>')

    # Top HUD Bar
    svg.append('  <!-- HUD Bar -->')
    svg.append(f'  <g transform="translate({margin_left}, 15)">')
    svg.append(
        '    <text x="0" y="16" fill="#58a6ff" font-size="13" font-weight="700" letter-spacing="0.5">🐍 GITHUB CONTRIBUTION SNAKE</text>'
    )
    svg.append('    <rect x="235" y="4" width="70" height="16" rx="4" fill="#238636" opacity="0.2" />')
    svg.append('    <rect x="235" y="4" width="70" height="16" rx="4" fill="none" stroke="#2ea043" stroke-width="1" />')
    svg.append('    <text x="270" y="16" fill="#3fb950" font-size="9.5" font-weight="700" text-anchor="middle">LIVE DATA</text>')

    stats_x = 325
    svg.append(
        f'    <text x="{stats_x}" y="16" fill="#8b949e" font-size="11">🍎 SCORE: <tspan fill="#ffd700" font-weight="700">{total_score:,} PTS</tspan></text>'
    )
    svg.append(
        f'    <text x="{stats_x + 130}" y="16" fill="#8b949e" font-size="11">🍏 FOOD: <tspan fill="#39d353" font-weight="700">{len(food_days)}</tspan></text>'
    )
    svg.append(
        f'    <text x="{stats_x + 215}" y="16" fill="#8b949e" font-size="11">🔥 STREAK: <tspan fill="#ff7b72" font-weight="700">{max_streak}D</tspan></text>'
    )

    svg.append(f'    <rect x="0" y="28" width="{grid_width}" height="3" rx="1.5" fill="#21262d" />')
    svg.append('    <rect class="hud-prog" x="0" y="28" height="3" rx="1.5" fill="url(#hudGrad)" />')
    svg.append('  </g>')

    # Month Labels
    svg.append('  <!-- Month Labels -->')
    svg.append('  <g>')
    for name, x in month_labels:
        svg.append(f'    <text x="{x}" y="{margin_top - 8}" fill="#7d8590" font-size="10">{name}</text>')
    svg.append('  </g>')

    # Weekday Labels
    svg.append('  <!-- Weekday Labels -->')
    svg.append(f'  <g fill="#7d8590" font-size="9" text-anchor="end">')
    svg.append(f'    <text x="{margin_left - 8}" y="{margin_top + 1 * pitch + 8}">Mon</text>')
    svg.append(f'    <text x="{margin_left - 8}" y="{margin_top + 3 * pitch + 8}">Wed</text>')
    svg.append(f'    <text x="{margin_left - 8}" y="{margin_top + 5 * pitch + 8}">Fri</text>')
    svg.append('  </g>')

    # Grid Cells (Empty days)
    svg.append('  <!-- Empty Background Grid Cells -->')
    svg.append('  <g>')
    for d in all_days:
        gx = margin_left + d["col"] * pitch
        gy = margin_top + d["row"] * pitch
        svg.append(
            f'    <rect x="{gx}" y="{gy}" width="{cell_size}" height="{cell_size}" rx="2.5" fill="#161b22" stroke="#21262d" stroke-width="0.5" />'
        )
    svg.append('  </g>')

    # Food Pellets (ONLY contributionCount >= 1)
    svg.append('  <!-- Real Contribution Food Pellets (count >= 1) -->')
    svg.append('  <g>')
    for d in food_days:
        c, r = d["col"], d["row"]
        gx = margin_left + c * pitch
        gy = margin_top + r * pitch
        tier, color, pts = get_tier_info(d["count"])
        svg.append(
            f'    <rect id="food-{c}-{r}" x="{gx}" y="{gy}" width="{cell_size}" height="{cell_size}" rx="2.5" fill="{color}" style="animation: eat_{c}_{r} {total_duration}s linear infinite; transform-box: fill-box; transform-origin: center;" />'
        )
    svg.append('  </g>')

    # Snake Elements (Tail to Head)
    svg.append('  <!-- Animated Snake Body & Head -->')
    svg.append('  <g>')
    body_styles = [
        ("snake-b4", 4.4, "#196c2e"),
        ("snake-b3", 4.8, "#238636"),
        ("snake-b2", 5.2, "#2ea043"),
        ("snake-b1", 5.6, "#3fb950"),
    ]
    for cls_name, rad, color in body_styles:
        svg.append(
            f'    <circle class="{cls_name}" cx="0" cy="0" r="{rad}" fill="{color}" stroke="#0d1117" stroke-width="0.8" />'
        )

    # Snake Head + glowing core
    svg.append('    <circle class="snake-head" cx="0" cy="0" r="6.2" fill="#00f7ff" stroke="#ffffff" stroke-width="1.2" />')
    svg.append('    <circle class="snake-head" cx="0" cy="0" r="2.5" fill="#ffffff" opacity="0.9" />')
    svg.append('  </g>')

    # Footer
    foot_y = total_height - 6
    svg.append(f'  <!-- Footer Stats -->')
    svg.append(f'  <g transform="translate({margin_left}, {foot_y})">')
    svg.append(f'    <text x="0" y="0" fill="#484f58" font-size="9">TARGET: @{user}</text>')
    svg.append(f'    <text x="120" y="0" fill="#484f58" font-size="9">CONTRIBUTIONS: {total_contributions:,}</text>')
    svg.append(f'    <text x="245" y="0" fill="#484f58" font-size="9">SPEED: FAST (80ms/cell)</text>')
    svg.append(
        f'    <text x="{grid_width}" y="0" fill="#484f58" font-size="9" text-anchor="end">FOOD TIERS: 🟩 1-2 · 🟦 3-5 · 🟨 6-10 · 🟪 10+</text>'
    )
    svg.append('  </g>')

    svg.append('</svg>')

    stats = {
        "user": user,
        "total_contributions": total_contributions,
        "contribution_days": len(food_days),
        "food_cells": len(food_days),
        "empty_cells": len(empty_days),
        "curr_streak": curr_streak,
        "max_streak": max_streak,
        "total_score": total_score,
        "total_steps": total_steps,
        "total_duration": total_duration,
        "num_weeks": num_weeks,
    }
    return "\n".join(svg), stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate Custom Animated GitHub Contribution Snake Game SVG."
    )
    parser.add_argument(
        "--user",
        default=TARGET_USER,
        help=f"Target GitHub username (default: {TARGET_USER})",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("output", "github-snake.svg"),
        help="Path to output SVG file",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (optional)",
    )
    args = parser.parse_args()

    # Step 1: Retrieve real GitHub contribution data
    cal_data = get_contribution_calendar(args.user, args.token)

    # Step 2: Build game SVG
    svg_content, stats = build_snake_game_svg(cal_data, args.user)

    # Step 3: Print Verification Information
    print("\n" + "=" * 55)
    print("           GAME VERIFICATION INFORMATION")
    print("=" * 55)
    print(f"Target user:               {stats['user']}")
    print(f"Total contribution count:  {stats['total_contributions']}")
    print(f"Contribution days:         {stats['contribution_days']}")
    print(f"Food cells:                {stats['food_cells']}")
    print(f"Empty cells:               {stats['empty_cells']}")
    print(f"Current streak:            {stats['curr_streak']} days")
    print(f"Maximum streak:            {stats['max_streak']} days")
    print(f"Total game score:          {stats['total_score']} PTS")
    print(f"Actual calendar weeks:     {stats['num_weeks']} weeks")
    print(f"Game path length:          {stats['total_steps']} steps ({stats['total_duration']}s)")
    print("=" * 55)

    # Step 4: Validate rules
    if stats["food_cells"] != stats["contribution_days"]:
        raise AssertionError("Validation failed: food_cells != contribution_days")
    if stats["food_cells"] == 0:
        raise AssertionError("Validation failed: No food cells found")
    if stats["empty_cells"] == 0:
        raise AssertionError("Validation failed: No empty cells found")

    # Step 5: Save file
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"[+] Successfully wrote generated SVG to: {args.output}")

    # Step 6: Validate XML syntax
    try:
        ET.fromstring(svg_content)
        print("[+] XML Validation: PASSED (SVG is well-formed XML)")
    except Exception as e:
        raise AssertionError(f"XML Validation FAILED: {e}")

    print("[+] All verification criteria passed successfully!\n")


if __name__ == "__main__":
    main()
