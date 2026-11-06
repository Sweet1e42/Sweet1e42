"""Генерирует SVG-карточки статистики GitHub для профиля (stats, languages, calendar)."""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from html import escape

USER = os.environ.get("GH_USER", "Sweet1e42")
OUT = os.environ.get("OUT_DIR", "metrics")

BG, BORDER = "#1a1b27", "#1a1b27"
TITLE, TEXT, ICON, MUTED = "#70a5fd", "#38bdae", "#bf91f3", "#a9b1d6"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
  }
}
"""


def gql(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data or not data.get("data", {}).get("user"):
        raise RuntimeError(data.get("errors"))
    return data["data"]["user"]


def fetch():
    tokens = [os.environ.get("METRICS_TOKEN", "").strip(), os.environ.get("GITHUB_TOKEN", "").strip()]
    last = None
    for t in tokens:
        if not t or any(c.isspace() for c in t):
            continue
        try:
            return gql(t)
        except (urllib.error.HTTPError, RuntimeError) as e:
            print(f"token failed: {e}", file=sys.stderr)
            last = e
    raise SystemExit(f"Нет рабочего токена: {last}")


def card(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
.t{{font:600 18px {FONT};fill:{TITLE}}}
.l{{font:600 14px {FONT};fill:{TEXT}}}
.v{{font:700 14px {FONT};fill:{MUTED}}}
.s{{font:400 11px {FONT};fill:{MUTED}}}
</style>
<rect x="0.5" y="0.5" rx="4.5" width="{w-1}" height="{h-1}" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="35" class="t">{escape(title)}</text>
{body}
</svg>
"""


def stats_svg(u):
    repos = u["repositories"]
    cc = u["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    rows = [
        ("★", "Звёзд получено", stars),
        ("⎇", "Коммитов за год", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("⇄", "Pull requests", u["pullRequests"]["totalCount"]),
        ("!", "Issues", u["issues"]["totalCount"]),
        ("▣", "Репозиториев", repos["totalCount"]),
        ("♥", "Подписчиков", u["followers"]["totalCount"]),
    ]
    body = ""
    for i, (ic, label, val) in enumerate(rows):
        y = 70 + i * 24
        body += (
            f'<text x="25" y="{y}" class="l" style="fill:{ICON}">{ic}</text>'
            f'<text x="48" y="{y}" class="l">{escape(label)}:</text>'
            f'<text x="250" y="{y}" class="v">{val}</text>\n'
        )
    name = u["name"] or u["login"]
    return card(400, 220, f"Статистика {name}", body)


def languages_svg(u):
    sizes, colors = {}, {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#888888"
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda x: -x[1])[:6]
    bar_w, x = 300, 25.0
    bar = ""
    for n, s in top:
        w = bar_w * s / total
        bar += f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="8" fill="{colors[n]}"/>'
        x += w
    bar = f'<clipPath id="c"><rect x="25" y="55" width="{bar_w}" height="8" rx="4"/></clipPath><g clip-path="url(#c)">{bar}</g>'
    items = ""
    for i, (n, s) in enumerate(top):
        cx = 25 + (i % 2) * 150
        cy = 92 + (i // 2) * 26
        items += (
            f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{colors[n]}"/>'
            f'<text x="{cx+16}" y="{cy}" class="s" style="font-size:12px">{escape(n)} {100*s/total:.1f}%</text>\n'
        )
    if not top:
        items = '<text x="25" y="95" class="s">Нет данных</text>'
    return card(350, 220, "Языки", bar + items)


def calendar_svg(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    levels = ["#21262d", "#2b2f6b", "#3d44a8", "#5865F2", "#8A2BE2"]
    mx = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0) or 1
    cell, gap, x0, y0 = 11, 3, 25, 70
    rects, months, last_m = "", "", None
    names = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            lvl = 0 if c == 0 else min(4, 1 + int(3 * c / mx))
            x = x0 + wi * (cell + gap)
            y = y0 + d["weekday"] * (cell + gap)
            rects += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{levels[lvl]}"><title>{d["date"]}: {c}</title></rect>'
        m = date.fromisoformat(w["contributionDays"][0]["date"]).month
        if m != last_m:
            months += f'<text x="{x0 + wi*(cell+gap)}" y="{y0-8}" class="s">{names[m-1]}</text>'
            last_m = m
    width = x0 * 2 + len(weeks) * (cell + gap)
    total = cal["totalContributions"]
    body = months + rects + f'<text x="{x0}" y="{y0 + 7*(cell+gap) + 18}" class="s">{total} вкладов за последний год</text>'
    return card(width, y0 + 7 * (cell + gap) + 35, "Активность", body)


def main():
    u = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("stats", stats_svg), ("languages", languages_svg), ("calendar", calendar_svg)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(u))
        print(f"{OUT}/{name}.svg ok")


if __name__ == "__main__":
    main()
