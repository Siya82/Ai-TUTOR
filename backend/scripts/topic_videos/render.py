"""
Renders the one-minute "What is this topic?" videos (ADR-049) from
content.py. A developer tool, not part of the API: it needs Playwright
(with Chromium) and ffmpeg.

    python -m scripts.topic_videos.render                    # every topic with content
    python -m scripts.topic_videos.render --only "Exponents" # one topic
    python -m scripts.topic_videos.render --stills           # pictures only, to check the layout

Writes media/topic-videos/<slug>.mp4 (720p, silent, about 1 MB each, to
keep learners' data costs down). Then register them with
    python -m scripts.topic_videos.register
"""

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.seed_dev_data import SUBJECTS
from scripts.topic_videos.content import CONTENT

BACKEND = Path(__file__).resolve().parents[2]
FRONTEND = BACKEND.parent / "frontend"
OUT = BACKEND / "media" / "topic-videos"
W, H = 1280, 720
FPS = 30
BG = "#0F1D3D"
GREEN = "#22C55E"
WS = ["ABOUT", "EXPECT", "BUILDS ON", "EXAMPLE 1", "EXAMPLE 2"]
SUBJECT_LABEL = {"Pure Mathematics": "Mathematics"}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def video_slug(subject: str, grade: int, topic: str) -> str:
    return f"g{grade}-{slugify(subject)}-{slugify(topic)}"


def topic_links(subject: str, grade: int, topic: str) -> tuple[list[str], list[str]]:
    """(builds on, leads to), from the seed's prerequisite chains."""
    spec = next(s for s in SUBJECTS if s["name"] == subject and s["grade"] == grade)
    prereq = dict(spec["topics"])
    builds_on = [prereq[topic]] if prereq.get(topic) else []
    leads_to = [name for name, pre in spec["topics"] if pre == topic]
    nxt = next((s for s in SUBJECTS if s["name"] == subject and s["grade"] == grade + 1), None)
    if nxt:  # the same topic one grade up is its most direct next step
        names = [name for name, _ in nxt["topics"]]
        same = [n for n in names if n == topic or n.startswith(topic + ":") or topic in n]
        if same:
            leads_to = [f"{same[0]} (Grade {grade + 1})"] + leads_to
        elif not leads_to:
            leads_to = [f"{name} (Grade {grade + 1})" for name, pre in nxt["topics"] if pre == topic]
    return builds_on, leads_to[:3]


def esc(s: str) -> str:
    """HTML-escape outside $...$ maths (KaTeX renders the maths later)."""
    parts = re.split(r"(\$[^$]+\$)", s)
    out = []
    for p in parts:
        if p.startswith("$") and p.endswith("$") and len(p) > 1:
            out.append(p)
        else:
            out.append(p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


def words(s: str) -> int:
    return len(re.sub(r"\$[^$]+\$", " formula ", s).split())


def hold(text_words: int, base: float = 2.2, rate: float = 2.6, lo: float = 4.0, hi: float = 11.0) -> float:
    """Seconds to leave a frame up: enough for a Grade 10 learner to read it."""
    return round(min(hi, max(lo, base + text_words / rate)), 1)


CSS = (
    "".join(
        f"@font-face{{font-family:P;font-weight:{w};src:url('{(FRONTEND / 'node_modules/@fontsource/poppins/files').as_uri()}/poppins-latin-{w}-normal.woff2')}}"
        for w in (400, 500, 600, 700)
    )
    + f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;overflow:hidden;font-family:P,sans-serif;color:#fff;
 background:radial-gradient(900px 520px at 85% 15%, rgba(34,197,94,.16) 0%, rgba(15,29,61,0) 70%), {BG}}}
.top{{position:absolute;left:48px;right:48px;top:32px;display:flex;align-items:center;justify-content:space-between}}
.crumb{{display:flex;align-items:center;gap:14px;font-size:17px;color:#9FB0D0;font-weight:500}}
.crumb img{{width:34px;height:34px;border-radius:8px}}
.crumb b{{color:#fff;font-weight:600}}
.ws{{display:flex;gap:8px}}
.ws span{{font-size:13px;font-weight:700;letter-spacing:.12em;padding:6px 11px;border-radius:999px;color:#7F8FB0;border:1.5px solid #2A3A62}}
.ws span.on{{background:{GREEN};border-color:{GREEN};color:{BG}}}
.ws span.done{{color:{GREEN};border-color:rgba(34,197,94,.45)}}
.stage{{position:absolute;left:72px;right:72px;top:112px;bottom:64px;display:flex;flex-direction:column;justify-content:center}}
.q{{font-size:20px;font-weight:700;letter-spacing:.16em;color:{GREEN};margin-bottom:14px}}
h1{{font-size:46px;line-height:1.15;font-weight:700;margin-bottom:26px}}
.body{{font-size:31px;line-height:1.45;color:#DCE4F4;max-width:1060px}}
.row{{display:flex;gap:44px;align-items:center}}
.row .body{{flex:1}}
.stack .visual{{margin-top:30px;display:inline-block;max-width:100%}}
.card{{background:rgba(255,255,255,.06);border:1.5px solid rgba(255,255,255,.12);border-radius:20px;padding:30px 34px}}
.visual{{flex:0 0 470px;font-size:30px;text-align:center;color:#fff}}
.places{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}}
.places .card{{font-size:25px;line-height:1.4;color:#DCE4F4;min-height:190px}}
.num{{display:inline-flex;width:40px;height:40px;border-radius:12px;background:{GREEN};color:{BG};font-weight:700;font-size:22px;align-items:center;justify-content:center;margin-bottom:16px}}
.chips{{display:flex;flex-wrap:wrap;gap:16px}}
.chips span{{font-size:30px;font-weight:600;padding:16px 28px;border-radius:16px;background:rgba(34,197,94,.14);border:1.5px solid rgba(34,197,94,.4)}}
.flow{{display:flex;align-items:stretch;gap:18px}}
.flow .card{{flex:1;font-size:25px;line-height:1.4}}
.flow .lab{{font-size:15px;font-weight:700;letter-spacing:.14em;color:#9FB0D0;margin-bottom:10px}}
.flow .me{{border-color:{GREEN};background:rgba(34,197,94,.12)}}
.arrow{{align-self:center;font-size:40px;color:{GREEN}}}
.paper{{margin-top:26px;font-size:24px;color:#C9D3E8}}
.paper b{{color:#fff}}
.problem{{font-size:30px;line-height:1.45;margin-bottom:22px}}
ol{{list-style:none;counter-reset:s}}
ol li{{counter-increment:s;font-size:27px;line-height:1.45;color:#DCE4F4;margin-bottom:14px;padding-left:52px;position:relative}}
ol li:before{{content:counter(s);position:absolute;left:0;top:2px;width:36px;height:36px;border-radius:10px;background:#2A3A62;color:#fff;font-weight:700;font-size:20px;display:flex;align-items:center;justify-content:center}}
ol li.new:before{{background:{GREEN};color:{BG}}}
.ans{{margin-top:12px;font-size:29px;font-weight:600;color:#fff;background:rgba(34,197,94,.16);border-left:6px solid {GREEN};padding:16px 22px;border-radius:12px}}
.center{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 90px}}
.kicker{{font-size:20px;font-weight:700;letter-spacing:.2em;color:{GREEN};margin-bottom:22px}}
.big{{font-size:68px;font-weight:700;line-height:1.1;margin-bottom:22px}}
.sub{{font-size:28px;color:#C9D3E8}}
.brand{{position:absolute;bottom:26px;right:48px;font-size:18px;font-weight:700;color:#7F8FB0;letter-spacing:.04em}}
.brand span{{color:{GREEN}}}
.katex{{font-size:1.02em}}
.why{{margin-top:30px;font-size:26px;line-height:1.45;color:#C9D3E8;max-width:1060px}}
.why b{{color:{GREEN}}}
.h1s{{font-size:36px;margin-bottom:22px}}
ul.ticks{{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:14px 34px}}
ul.ticks li{{font-size:25px;line-height:1.4;color:#DCE4F4;padding-left:42px;position:relative}}
ul.ticks li:before{{content:"✓";position:absolute;left:0;top:0;width:30px;height:30px;border-radius:9px;background:{GREEN};color:{BG};font-weight:700;font-size:18px;display:flex;align-items:center;justify-content:center}}
ul.plain{{list-style:none}}
ul.plain li{{margin-bottom:12px;font-size:22px;line-height:1.35}}
.also{{margin-top:16px;font-size:19px;color:#C9D3E8;line-height:1.35}}
.also b{{color:#fff;font-weight:600}}
"""
)


def page(body: str) -> str:
    katex = (FRONTEND / "node_modules/katex/dist").as_uri()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{katex}/katex.min.css"><style>{CSS}</style>
<script src="{katex}/katex.min.js"></script><script src="{katex}/contrib/auto-render.min.js"></script>
</head><body>{body}<div class="brand">THUTO<span>ra</span></div>
<script>renderMathInElement(document.body,{{delimiters:[{{left:"$$",right:"$$",display:true}},{{left:"$",right:"$",display:false}}],throwOnError:false}});document.body.dataset.ready=1</script>
</body></html>"""


def example_frames(chrome, label: str, ex: dict, fade_in: bool, fade_out: bool) -> list[tuple[str, float, str]]:
    """A worked example revealed one line at a time: question, each step, answer."""
    out = []
    steps = ex["steps"]
    last = len(steps) + 1
    for k in range(last + 1):
        shown = steps[: max(0, k)]
        lis = "".join(f'<li class="{"new" if i == k - 1 else ""}">{esc(s)}</li>' for i, s in enumerate(shown))
        ans = f'<div class="ans">{esc(ex["a"])}</div>' if k == last else ""
        secs = (hold(words(ex["q"]), lo=4.0, hi=8) if k == 0
                else hold(words(steps[k - 1]), base=1.5, rate=2.8, lo=3.0, hi=7) if k < last
                else 4.5)
        fade = ("in" if fade_in and k == 0 else "") + ("out" if fade_out and k == last else "")
        fade = {"inout": "both"}.get(fade, fade)
        out.append((page(chrome + f"""<div class="stage"><div class="q">{label}</div>
            <div class="problem">{esc(ex['q'])}</div><ol>{lis}</ol>{ans}</div>"""), secs, fade))
    return out


def frames_for(subject: str, grade: int, topic: str, c: dict) -> list[tuple[str, float, str]]:
    """[(html, seconds, fade)] -- fade is 'in', 'out', 'both' or ''. The order
    must match narration.narration()."""
    label = SUBJECT_LABEL.get(subject, subject)
    logo = (FRONTEND / "public/thutora-learn-logo.png").as_uri()

    def chrome(step: int) -> str:
        ws = "".join(
            f'<span class="{"on" if i == step else "done" if i < step else ""}">{w}</span>' for i, w in enumerate(WS)
        )
        return (f'<div class="top"><div class="crumb"><img src="{logo}">Grade {grade} · {label} · '
                f'<b>{esc(topic)}</b></div><div class="ws">{ws}</div></div>')

    out = []
    out.append((page(f"""<div class="center"><div class="kicker">TOPIC INDUCTION</div>
        <div class="big">{esc(topic)}</div><div class="sub">Grade {grade} · {label} · {c['paper']}</div></div>"""), 4.0, "both"))

    visual = f'<div class="card visual">$$ {c["visual"]} $$</div>' if c.get("visual") else ""
    layout = "stack" if len(c.get("visual", "")) > 45 else "row"
    out.append((page(chrome(0) + f"""<div class="stage"><div class="q">WHAT IT'S ABOUT</div>
        <div class="{layout}"><div class="body">{esc(c['what'])}</div>{visual}</div>
        <div class="why"><b>Why it matters:</b> {esc(c['why'])}</div></div>"""),
        hold(words(c["what"]) + words(c["why"]) + 4, hi=14), "both"))

    items = "".join(f"<li>{esc(x)}</li>" for x in c["expect"])
    out.append((page(chrome(1) + f"""<div class="stage"><div class="q">WHAT TO EXPECT</div>
        <h1 class="h1s">In this topic you'll learn:</h1><ul class="ticks">{items}</ul></div>"""),
        hold(sum(words(x) for x in c["expect"]) + 4, hi=14), "both"))

    builds_on, leads_to = topic_links(subject, grade, topic)
    prev = "".join(f"<li>{esc(re.sub(rf'^Grade {grade - 1} ', '', x))}</li>" for x in c["previous"])
    also = (f'<div class="also">In Grade {grade} it also uses<br><b>{"<br>".join(map(esc, builds_on))}</b></div>'
            if builds_on else "")
    after = ('<ul class="plain">' + "".join(f"<li>{esc(t)}</li>" for t in leads_to) + "</ul>"
             if leads_to else "Harder problems in later grades")
    out.append((page(chrome(2) + f"""<div class="stage"><div class="q">WHERE IT COMES FROM</div>
        <div class="flow"><div class="card"><div class="lab">FROM GRADE {grade - 1}</div><ul class="plain">{prev}</ul></div>
        <div class="arrow">→</div>
        <div class="card me"><div class="lab">YOU ARE HERE</div><b>{esc(topic)}</b>{also}</div><div class="arrow">→</div>
        <div class="card"><div class="lab">LEADS TO</div>{after}</div></div>
        <div class="paper">In your final exam it's in <b>{c['paper']}</b>.</div></div>"""),
        hold(sum(words(x) for x in c["previous"]) + 12, hi=12), "both"))

    ex1, ex2 = c["examples"]
    out += example_frames(chrome(3), "EXAMPLE 1 · WARM-UP", ex1, True, True)
    out += example_frames(chrome(4), "EXAMPLE 2 · EXAM STYLE", ex2, True, True)

    out.append((page(f"""<div class="center"><div class="kicker">READY?</div>
        <div class="big" style="font-size:50px">You're set to start<br>{esc(topic)}</div>
        <div class="sub">Stuck on anything? Ask THUTOra in LEARN: it explains step by step.</div></div>"""), 4.5, "both"))
    return out


def audio_seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


VOICE_LEAD = 0.35  # seconds of quiet before the narrator starts a scene
VOICE_TAIL = 0.6   # and after they finish, before the next scene


def encode(png: Path, secs: float, fade: str, out: Path, audio: Path | None = None, voiced: bool = False) -> None:
    """One scene. With `voiced`, every scene gets an audio track (silence if
    `audio` is None) so the scenes join without re-encoding."""
    n = round(secs * FPS)
    vf = [f"scale={W}:{H}:flags=lanczos", "format=yuv420p", "loop=-1:1", f"trim=end_frame={n}", f"setpts=N/{FPS}/TB"]
    if fade in ("in", "both"):
        vf.append(f"fade=t=in:st=0:d=0.35:color={BG}")
    if fade in ("out", "both"):
        vf.append(f"fade=t=out:st={secs - 0.35:.2f}:d=0.35:color={BG}")
    tmp = out.with_suffix(".tmp.mp4")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(png)]
    if voiced:
        if audio is not None:
            cmd += ["-i", str(audio)]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
        delay = int(VOICE_LEAD * 1000)
        af = f"adelay={delay}:all=1,apad,atrim=0:{secs:.3f},afade=t=out:st={max(0, secs - 0.15):.3f}:d=0.15"
        cmd += ["-filter_complex", f"[0:v]{','.join(vf)}[v];[1:a]{af},aresample=24000[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "26",
            "-r", str(FPS), "-g", str(FPS * 10), "-pix_fmt", "yuv420p"]
    if voiced:
        cmd += ["-c:a", "aac", "-b:a", "48k", "-ac", "1", "-ar", "24000", "-t", f"{secs:.3f}"]
    subprocess.run(cmd + [str(tmp)], check=True)
    tmp.rename(out)


def render(subject: str, grade: int, topic: str, c: dict, browser, stills: bool,
           voice: str | None = None, out_dir: Path | None = None) -> Path:
    slug = video_slug(subject, grade, topic)
    frames = frames_for(subject, grade, topic, c)
    audio_dir = OUT / "voice" / voice / slug if voice else None
    if audio_dir is not None and not audio_dir.exists():
        raise SystemExit(f"No narration for {topic} in {audio_dir}: run scripts.topic_videos.voice first.")
    target_dir = out_dir or OUT
    work = Path(tempfile.mkdtemp(prefix=f"tv-{slug}-"))
    pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
    clips = []
    for i, (html, secs, fade) in enumerate(frames):
        f = work / f"{i:02d}.html"
        f.write_text(html, encoding="utf-8")
        pg.goto(f.as_uri())
        pg.wait_for_selector("body[data-ready]")
        pg.evaluate("document.fonts.ready")
        png = work / f"{i:02d}.png"
        pg.screenshot(path=str(png))
        if stills:
            (OUT / "stills").mkdir(parents=True, exist_ok=True)
            shutil.copy(png, OUT / "stills" / f"{slug}-{i:02d}.png")
        else:
            clip = work / f"{i:02d}.mp4"
            audio = None
            if audio_dir is not None:
                mp3 = next((p for p in (audio_dir / f"{i:02d}.mp3", audio_dir / f"{i:02d}.wav") if p.exists()), None)
                if mp3 is not None:
                    audio = mp3
                    # the scene lasts as long as the narrator needs, never less than reading time
                    secs = round(max(secs, VOICE_LEAD + audio_seconds(mp3) + VOICE_TAIL), 2)
            encode(png, secs, fade, clip, audio, voiced=audio_dir is not None)
            clips.append(clip)
    pg.close()
    target = target_dir / f"{slug}.mp4"
    if not stills:
        target_dir.mkdir(parents=True, exist_ok=True)
        (work / "list.txt").write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
        tmp = target_dir / f"{slug}.tmp.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
                        "-c", "copy", "-movflags", "+faststart", str(tmp)], check=True)
        tmp.replace(target)
    shutil.rmtree(work, ignore_errors=True)
    return target


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="render just this topic name")
    ap.add_argument("--stills", action="store_true", help="save PNGs instead of video")
    ap.add_argument("--chrome", help="path to a Chrome/Chromium executable (default: Playwright's)")
    ap.add_argument("--voice", help="add narration made by scripts.topic_videos.voice with this voice, e.g. en-ZA-LeahNeural")
    ap.add_argument("--out", help="write the videos here instead of media/topic-videos (e.g. for samples)")
    a = ap.parse_args()
    out_dir = Path(a.out) if a.out else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=a.chrome) if a.chrome else p.chromium.launch()
        for (subject, grade), topics in CONTENT.items():
            for topic, c in topics.items():
                if a.only and topic != a.only:
                    continue
                path = render(subject, grade, topic, c, browser, a.stills, a.voice, out_dir)
                if not a.stills:
                    secs = float(subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                        capture_output=True, text=True, check=True).stdout)
                    manifest[path.name] = {"subject": subject, "grade": grade, "topic": topic,
                                           "seconds": round(secs), "voice": a.voice,
                                           "reviewed_by": c.get("reviewed_by")}
                    print(f"{path.name}: {secs:.0f} s, {path.stat().st_size / 1e6:.1f} MB")
        browser.close()
    if not a.stills:
        manifest_path.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
