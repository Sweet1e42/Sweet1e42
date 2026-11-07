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


INVITE = os.environ.get("DISCORD_INVITE", "XtyfDvn6Xe")


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def data_uri(url, mime):
    import base64
    try:
        return f"data:{mime};base64," + base64.b64encode(http_get(url)).decode()
    except Exception as e:
        print(f"image failed {url}: {e}", file=sys.stderr)
        return None


def wrap(text, width):
    text = text.split(". ")[0].rstrip(".") + "." if ". " in text else text
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1].rstrip(" ,.") + "…"
    return lines


def discord_svg(inv, banner, icon):
    g = inv["guild"]
    w, h = 640, 220
    bg = (
        f'<image href="{banner}" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#r)"/>'
        if banner else f'<rect width="{w}" height="{h}" fill="url(#g)"/>'
    )
    ic = (
        f'<image href="{icon}" x="28" y="62" width="96" height="96" clip-path="url(#ic)"/>'
        if icon else f'<circle cx="76" cy="110" r="48" fill="#5865F2"/>'
    )
    desc = "".join(
        f'<text x="148" y="{120 + i*20}" class="d">{escape(line)}</text>'
        for i, line in enumerate(wrap(g.get("description") or "", 52))
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
<clipPath id="r"><rect width="{w}" height="{h}" rx="12"/></clipPath>
<clipPath id="ic"><circle cx="76" cy="110" r="48"/></clipPath>
<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#5865F2"/><stop offset="1" stop-color="#8A2BE2"/></linearGradient>
<linearGradient id="shade" x1="0" x2="1"><stop offset="0" stop-color="#0d1117" stop-opacity=".92"/><stop offset="1" stop-color="#0d1117" stop-opacity=".55"/></linearGradient>
</defs>
<style>
.n{{font:700 30px {FONT};fill:#fff}}
.d{{font:400 14px {FONT};fill:#c9d1d9}}
.c{{font:600 14px {FONT};fill:#fff}}
.b{{font:700 15px {FONT};fill:#fff}}
</style>
<g clip-path="url(#r)">{bg}<rect width="{w}" height="{h}" fill="url(#shade)"/></g>
<circle cx="76" cy="110" r="51" fill="#0d1117"/>{ic}
<text x="148" y="90" class="n">{escape(g["name"])}</text>
{desc}
<circle cx="154" cy="181" r="5" fill="#23a55a"/><text x="166" y="186" class="c">{inv.get("approximate_presence_count", 0)} онлайн</text>
<circle cx="268" cy="181" r="5" fill="#80848e"/><text x="280" y="186" class="c">{inv.get("approximate_member_count", 0)} участников</text>
<rect x="470" y="160" width="146" height="40" rx="8" fill="#5865F2"/>
<text x="543" y="186" class="b" text-anchor="middle">Присоединиться</text>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="none" stroke="#30363d"/>
</svg>
"""


def write_discord():
    try:
        inv = json.loads(http_get(f"https://discord.com/api/v10/invites/{INVITE}?with_counts=true"))
    except Exception as e:
        print(f"discord failed: {e}", file=sys.stderr)
        return
    g = inv["guild"]
    banner = icon = None
    if g.get("banner"):
        banner = data_uri(f"https://cdn.discordapp.com/banners/{g['id']}/{g['banner']}.jpg?size=640", "image/jpeg")
    if g.get("icon"):
        icon = data_uri(f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png?size=128", "image/png")
    with open(os.path.join(OUT, "discord.svg"), "w", encoding="utf-8") as f:
        f.write(discord_svg(inv, banner, icon))
    print(f"{OUT}/discord.svg ok")


def main():
    os.makedirs(OUT, exist_ok=True)
    write_discord()
    u = fetch()
    for name, fn in [("stats", stats_svg), ("languages", languages_svg), ("calendar", calendar_svg)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(u))
        print(f"{OUT}/{name}.svg ok")


if __name__ == "__main__":
    main()
