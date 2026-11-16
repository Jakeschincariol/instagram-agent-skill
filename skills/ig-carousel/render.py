#!/usr/bin/env python3
"""
render.py - render a carousel from a design system: theme tokens plus slide
content in, an HTML page and 1080x1350 PNGs (one per slide) out.

The theme holds everything that makes a deck recognisably one brand: colours,
fonts, the logo and where it sits, slide numbering, text limits. The slides
hold only content and a layout name. Change the theme and every deck changes
with it; nothing about the look lives in the copy.

Layouts
  cover      eyebrow, title, subtitle, visual            the hook
  statement  one large line and a short support line      the stake, a turn
  list       title and up to 5 items                      reasons, checks
  steps      title and up to 4 numbered steps             a process
  compare    title and two columns                        A vs B, before/after
  stat       a number, what it means, and its source      data (source required)
  myth       the myth and the fact                        myths and facts
  quote      a quote and who said it                      a buyer's words
  visual     a full-bleed visual with a caption           a 3D concept, a photo
  cta        title, one action, a keyword                 the last slide

Any slide may carry a "source" line (the stat layout requires one).

A visual is an image file, or, when there is none yet, a labelled panel that
carries the prompt or shot description for the image the creator will make or
generate. The renderer never invents an image and never fills a stat.

Usage
  python3 render.py slides.json --theme themes/editorial.json --out out/
  python3 render.py slides.json --out out/ --png          # also PNGs (needs node + playwright)
  python3 render.py slides.json --check                   # checks only, nothing written

Exit status: 0 rendered, 1 warnings with --strict or errors, 2 bad input.
"""

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_THEME = os.path.join(HERE, "themes", "editorial.json")
DEVA = re.compile("[" + chr(0x0900) + "-" + chr(0x097F) + "]")
LAYOUTS = {"cover", "statement", "list", "steps", "compare", "stat", "myth", "quote", "visual", "cta"}
# Fonts known to carry Devanagari. A Hindi slide needs one of them in its stack.
DEVANAGARI_FONTS = {"mukta", "hind", "noto sans devanagari", "tiro devanagari hindi", "poppins devanagari",
                    "baloo 2", "yatra one", "khand", "rajdhani", "teko", "martel", "martel sans", "kalam",
                    "anek devanagari", "gotu", "eczar", "amita", "karma", "sarala", "yantramanav"}
LIMITS = {"title": 60, "subtitle": 110, "eyebrow": 32, "text": 150, "support": 140, "item": 80,
          "value": 12, "label": 90, "quote": 180, "action": 70, "caption": 120}
MAX_ITEMS = {"list": 5, "steps": 4, "compare": 4}


class BadInput(Exception):
    pass


def esc(s):
    return html.escape(str(s or ""))


def is_hi(text):
    return bool(DEVA.search(text or ""))


def load_theme(path):
    try:
        t = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise BadInput(f"cannot read theme {path}: {e}")
    t["_dir"] = os.path.dirname(os.path.abspath(path))
    for k in ("colors", "fonts"):
        if k not in t:
            raise BadInput(f"theme needs {k!r}")
    for c in ("bg", "ink", "accent", "muted", "soft", "highlight"):
        if c not in t["colors"]:
            raise BadInput(f"theme colors need {c!r}")
    return t


def asset(path, base):
    """An image as a data URI, so the HTML is self-contained."""
    p = path if os.path.isabs(path) else os.path.join(base, path)
    if not os.path.exists(p):
        return None
    mime = mimetypes.guess_type(p)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(p, "rb").read()).decode()


def check(deck, theme):
    """Problems a reviewer would send back. Errors stop the render; warnings do not."""
    errors, warnings = [], []
    slides = deck.get("slides") or []
    if not 2 <= len(slides) <= 20:
        errors.append(f"{len(slides)} slides: Instagram takes 2 to 20")
    limits = dict(LIMITS, **theme.get("limits", {}))
    stack = [f.lower() for f in theme["fonts"].get("display_stack", []) + theme["fonts"].get("body_stack", [])]
    for n, s in enumerate(slides, 1):
        lay = s.get("layout")
        if lay not in LAYOUTS:
            errors.append(f"slide {n}: unknown layout {lay!r}")
            continue
        if lay == "stat":
            if not s.get("value") or not s.get("source"):
                errors.append(f"slide {n}: a stat needs its value and a source. No source, no stat.")
        if lay in MAX_ITEMS:
            items = s.get("items") or s.get("left", {}).get("points", []) + s.get("right", {}).get("points", [])
            cap = MAX_ITEMS[lay] * (2 if lay == "compare" else 1)
            if len(items) > cap:
                warnings.append(f"slide {n}: {len(items)} items, keep it to {cap}: one idea per slide")
        for field, cap in limits.items():
            val = s.get(field)
            if isinstance(val, str) and len(val) > cap:
                warnings.append(f"slide {n}: {field} is {len(val)} characters, the {lay} layout holds {cap}")
        for it in s.get("items", []):
            text = it if isinstance(it, str) else it.get("text", "")
            if len(text) > limits["item"]:
                warnings.append(f"slide {n}: an item is {len(text)} characters, hold it to {limits['item']}")
        words = len(re.findall(r"\S+", " ".join(str(v) for v in s.values() if isinstance(v, str))))
        if words > 45:
            warnings.append(f"slide {n}: {words} words. A slide that needs a paragraph is two slides")
        if any(is_hi(v) for v in s.values() if isinstance(v, str)) and not any(f in DEVANAGARI_FONTS for f in stack):
            errors.append(f"slide {n} has Hindi but the theme's font stacks carry no Devanagari font")
    if slides and slides[0].get("layout") != "cover":
        warnings.append("slide 1 is not a cover: the first slide is the hook")
    if slides and slides[-1].get("layout") != "cta":
        warnings.append("the last slide is not a cta: end on one action")
    return errors, warnings


def visual(v, theme, cls="visual"):
    if not v:
        return ""
    if isinstance(v, str):
        v = {"prompt": v}
    uri = asset(v["image"], theme["_base"]) if v.get("image") else None
    if uri:
        return f'<div class="{cls}"><img src="{uri}" alt="{esc(v.get("alt", ""))}"></div>'
    label = "VISUAL TO CREATE" if v.get("prompt") else "VISUAL"
    return (f'<div class="{cls} placeholder"><div class="ph-orb"></div><div class="ph-text">'
            f'<b>{label}</b><span>{esc(v.get("prompt") or v.get("image", ""))}</span></div></div>')


def tx(s, cls, tag="div"):
    if not s:
        return ""
    lang = ' lang="hi"' if is_hi(s) else ""
    return f'<{tag} class="{cls}{" hi" if lang else ""}"{lang}>{esc(s)}</{tag}>'


def slide_html(s, n, total, theme, logo_uri):
    lay = s["layout"]
    b = theme.get("brand", {})
    num_style = theme.get("numbering", {}).get("style", "{n:02d} / {total:02d}")
    number = num_style.format(n=n, total=total)
    head = ""
    if logo_uri and lay in theme.get("logo_on", ["cover", "cta"]):
        head = f'<img class="logo" src="{logo_uri}" alt="{esc(b.get("name", ""))}">'
    elif b.get("name"):
        head = f'<div class="wordmark">{esc(b["name"])}</div>'
    foot = (f'<div class="foot"><span>{esc(b.get("handle", ""))}</span>'
            f'<span class="num">{esc(number)}</span></div>')
    body = ""
    if lay == "cover":
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("title"), "cover-title", "h1")
                + tx(s.get("subtitle"), "subtitle") + visual(s.get("visual"), theme, "visual cover-visual"))
    elif lay == "statement":
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("text"), "statement")
                + tx(s.get("support"), "support") + visual(s.get("visual"), theme, "visual small"))
    elif lay in ("list", "steps"):
        items = "".join(
            f'<li><span class="mark">{i:02d}</span>{tx(it if isinstance(it, str) else it.get("text"), "item")}'
            f'{tx("" if isinstance(it, str) else it.get("note"), "note")}</li>'
            for i, it in enumerate(s.get("items", []), 1))
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("title"), "title", "h2")
                + f'<ol class="{lay}">{items}</ol>')
    elif lay == "compare":
        col = lambda c, cls: (f'<div class="col {cls}">{tx(c.get("label"), "col-label")}<ul>'
                              + "".join(f"<li>{tx(p, 'item', 'span')}</li>" for p in c.get("points", []))
                              + "</ul></div>")
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("title"), "title", "h2")
                + f'<div class="cols">{col(s.get("left", {}), "left")}{col(s.get("right", {}), "right")}</div>')
    elif lay == "stat":
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("value"), "stat-value")
                + tx(s.get("label"), "stat-label") + tx("Source: " + s.get("source", ""), "source"))
    elif lay == "myth":
        body = (tx(s.get("eyebrow") or "Myth vs fact", "eyebrow")
                + f'<div class="myth-block">{tx(s.get("myth_label", "MYTH"), "tag")}{tx(s.get("myth"), "myth-text")}</div>'
                + f'<div class="fact-block">{tx(s.get("fact_label", "FACT"), "tag")}{tx(s.get("fact"), "fact-text")}</div>')
    elif lay == "quote":
        body = tx(s.get("quote"), "quote") + tx(s.get("by"), "by")
    elif lay == "visual":
        body = visual(s.get("visual"), theme, "visual full") + tx(s.get("caption"), "caption")
    elif lay == "cta":
        chip = f'<div class="chip">{esc(s["keyword"])}</div>' if s.get("keyword") else ""
        body = (tx(s.get("eyebrow"), "eyebrow") + tx(s.get("title"), "cta-title", "h2")
                + tx(s.get("action"), "action") + chip)
    if s.get("source") and lay != "stat":         # any slide may cite where its point comes from
        body += tx(s["source"], "source slide-source")
    deco = '<div class="orb"></div>' if lay in theme.get("orb_on", ["cover", "statement", "cta"]) else ""
    # "l-" keeps the layout name from colliding with element classes (.quote, .visual, .statement)
    return (f'<section class="slide l-{lay}" data-n="{n}">{deco}<header>{head}</header>'
            f'<main>{body}</main>{foot}</section>')


def css(theme):
    c, f = theme["colors"], theme["fonts"]
    W, H = theme.get("size", [1080, 1350])
    disp = ", ".join(f'"{x}"' for x in f.get("display_stack", ["Poppins", "Mukta"])) + ", sans-serif"
    body = ", ".join(f'"{x}"' for x in f.get("body_stack", ["Inter", "Mukta"])) + ", sans-serif"
    pad = theme.get("margin", 96)
    return f"""
:root {{ --bg:{c['bg']}; --ink:{c['ink']}; --accent:{c['accent']}; --muted:{c['muted']};
  --soft:{c['soft']}; --hl:{c['highlight']}; --disp:{disp}; --body:{body}; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#888; font-family:var(--body); }}
.slide {{ width:{W}px; height:{H}px; position:relative; overflow:hidden; background:var(--bg); color:var(--ink);
  padding:{pad}px; display:flex; flex-direction:column; margin:0 auto 40px; }}
header {{ height:64px; display:flex; align-items:center; position:relative; z-index:2; }}
.logo {{ height:{theme.get('logo_height', 56)}px; }}
.wordmark {{ font:700 26px var(--disp); letter-spacing:.02em; color:var(--accent); }}
main {{ flex:1; display:flex; flex-direction:column; justify-content:center; gap:28px; position:relative; z-index:2; }}
.foot {{ display:flex; justify-content:space-between; font:500 24px var(--body); color:var(--muted);
  position:relative; z-index:2; }}
.num {{ font-variant-numeric:tabular-nums; letter-spacing:.06em; }}
.orb {{ position:absolute; width:{int(W*0.9)}px; height:{int(W*0.9)}px; border-radius:50%;
  right:-{int(W*0.3)}px; top:-{int(W*0.25)}px; z-index:1;
  background:radial-gradient(circle at 35% 35%, var(--hl) 0%, var(--soft) 45%, transparent 70%); opacity:.55; }}
.eyebrow {{ font:600 26px var(--body); letter-spacing:.14em; text-transform:uppercase; color:var(--accent); }}
.cover-title {{ font:800 104px/1.02 var(--disp); letter-spacing:-.02em; max-width:92%; }}
h2.title, .cta-title {{ font:800 72px/1.06 var(--disp); letter-spacing:-.015em; }}
.subtitle, .support {{ font:400 36px/1.35 var(--body); color:var(--muted); max-width:88%; }}
.statement {{ font:700 76px/1.12 var(--disp); letter-spacing:-.01em; }}
.hi {{ line-height:1.32 !important; letter-spacing:0 !important; }}
.cover-title.hi {{ font-size:96px; }}
.visual {{ border-radius:32px; overflow:hidden; position:relative; }}
.visual img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.cover-visual {{ height:520px; margin-top:12px; }}
.visual.small {{ height:320px; }}
.visual.full {{ flex:1; min-height:780px; }}
.placeholder {{ background:linear-gradient(140deg, var(--soft), var(--bg)); border:3px dashed var(--accent);
  display:flex; align-items:flex-end; }}
.ph-orb {{ position:absolute; width:300px; height:300px; border-radius:50%; right:60px; top:60px;
  background:radial-gradient(circle at 30% 30%, var(--hl), var(--accent)); opacity:.35; }}
.ph-text {{ padding:32px; font:400 26px/1.4 var(--body); color:var(--ink); display:flex; flex-direction:column; gap:8px; }}
.ph-text b {{ font:700 20px var(--body); letter-spacing:.16em; color:var(--accent); }}
ol {{ list-style:none; display:flex; flex-direction:column; gap:26px; }}
ol li {{ display:grid; grid-template-columns:96px 1fr; align-items:baseline; column-gap:12px; }}
.mark {{ font:800 44px var(--disp); color:var(--accent); font-variant-numeric:tabular-nums; }}
.item {{ font:600 40px/1.3 var(--body); }}
.note {{ grid-column:2; font:400 28px/1.35 var(--body); color:var(--muted); }}
ol.steps li {{ border-left:4px solid var(--soft); padding-left:20px; }}
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; }}
.col {{ border-radius:28px; padding:36px; display:flex; flex-direction:column; gap:20px; }}
.col.left {{ background:rgba(0,0,0,.04); }}
.col.right {{ background:var(--soft); }}
.col ul {{ list-style:none; display:flex; flex-direction:column; gap:16px; }}
.col .item {{ font-size:32px; }}
.col-label {{ font:800 34px var(--disp); color:var(--accent); }}
.stat-value {{ font:800 220px/1 var(--disp); color:var(--accent); letter-spacing:-.03em; }}
.stat-label {{ font:600 44px/1.3 var(--body); max-width:90%; }}
.source {{ font:400 24px var(--body); color:var(--muted); }}
.myth-block, .fact-block {{ border-radius:28px; padding:40px; display:flex; flex-direction:column; gap:14px; }}
.myth-block {{ background:rgba(0,0,0,.05); }}
.myth-text {{ font:600 46px/1.25 var(--body); color:var(--muted); text-decoration:line-through;
  text-decoration-thickness:3px; }}
.fact-block {{ background:var(--accent); color:var(--bg); }}
.fact-text {{ font:700 50px/1.25 var(--disp); }}
.tag {{ font:700 22px var(--body); letter-spacing:.2em; }}
.quote {{ font:700 66px/1.2 var(--disp); }}
.quote::before {{ content:"\\201C"; display:block; font-size:160px; line-height:.6; color:var(--accent); }}
.by {{ font:500 30px var(--body); color:var(--muted); }}
.caption {{ font:600 34px/1.35 var(--body); }}
.action {{ font:500 40px/1.35 var(--body); max-width:90%; }}
.chip {{ align-self:flex-start; background:var(--accent); color:var(--bg); font:800 52px var(--disp);
  padding:18px 44px; border-radius:999px; letter-spacing:.04em; }}
"""


def render_html(deck, theme):
    theme["_base"] = deck.get("_base", theme["_dir"])
    logo = theme.get("brand", {}).get("logo")
    logo_uri = asset(logo, theme["_dir"]) if logo else None
    slides = deck["slides"]
    families = theme["fonts"].get("google", [])
    link = ""
    if families:
        q = "&".join("family=" + fam.replace(" ", "+") + ":wght@400;500;600;700;800" for fam in families)
        link = f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{q}&display=block">'
    body = "\n".join(slide_html(s, n, len(slides), theme, logo_uri) for n, s in enumerate(slides, 1))
    title = esc(deck.get("title", "carousel"))
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>{link}'
            f"<style>{css(theme)}</style></head><body>{body}</body></html>")


PNG_JS = r"""
const { chromium } = require('playwright');
const [,, html, outdir] = process.argv;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 1500 }, deviceScaleFactor: 1 });
  await p.goto('file://' + html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const slides = await p.$$('section.slide');
  for (let i = 0; i < slides.length; i++) {
    const f = outdir + '/slide_' + String(i + 1).padStart(2, '0') + '.png';
    await slides[i].screenshot({ path: f });
    console.log(f);
  }
  const missing = await p.evaluate(() => [...document.fonts].filter(f => f.status === 'error').map(f => f.family));
  if (missing.length) console.error('fonts failed to load: ' + missing.join(', '));
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
"""


def render_png(html_path, outdir):
    node = shutil.which("node")
    if not node:
        return None, "node is not installed: PNGs skipped, the HTML is complete"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(PNG_JS)
        js = fh.name
    try:
        p = subprocess.run([node, js, os.path.abspath(html_path), os.path.abspath(outdir)],
                           capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(js)
    if p.returncode != 0:
        return None, "PNG render failed: " + (p.stderr.strip().splitlines() or ["unknown error"])[-1]
    return p.stdout.split(), p.stderr.strip() or None


def main():
    ap = argparse.ArgumentParser(description="Render a carousel from a design system.")
    ap.add_argument("slides")
    ap.add_argument("--theme", help="theme JSON (default: the slides file's 'theme', else themes/editorial.json)")
    ap.add_argument("--out", default="carousel_out")
    ap.add_argument("--png", action="store_true", help="also write 1080x1350 PNGs (needs node + playwright)")
    ap.add_argument("--check", action="store_true", help="only run the checks")
    ap.add_argument("--strict", action="store_true", help="warnings fail the run")
    args = ap.parse_args()
    try:
        deck = json.load(open(args.slides, encoding="utf-8"))
        deck["_base"] = os.path.dirname(os.path.abspath(args.slides))
        tpath = args.theme or (os.path.join(deck["_base"], deck["theme"]) if deck.get("theme") else DEFAULT_THEME)
        theme = load_theme(tpath)
    except (OSError, json.JSONDecodeError, BadInput) as e:
        print(f"bad input: {e}", file=sys.stderr)
        sys.exit(2)
    errors, warnings = check(deck, theme)
    for e in errors:
        print(f"ERROR  {e}", file=sys.stderr)
    for w in warnings:
        print(f"WARN   {w}", file=sys.stderr)
    if errors:
        sys.exit(1)
    if args.check:
        print(f"{len(deck['slides'])} slides checked: {len(warnings)} warning(s)")
        sys.exit(1 if (warnings and args.strict) else 0)
    os.makedirs(args.out, exist_ok=True)
    html_path = os.path.join(args.out, "carousel.html")
    open(html_path, "w", encoding="utf-8").write(render_html(deck, theme))
    print(f"wrote {html_path}")
    if args.png:
        files, note = render_png(html_path, args.out)
        if files:
            print(f"wrote {len(files)} PNG(s) to {args.out}")
        if note:
            print(f"note: {note}", file=sys.stderr)
    sys.exit(1 if (warnings and args.strict) else 0)


if __name__ == "__main__":
    main()
