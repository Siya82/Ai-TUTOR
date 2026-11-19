"""
Makes the narration audio for the topic videos (ADR-049) with an Azure
neural voice. Runs on a machine that can reach Azure (your laptop), not in
the build sandbox. Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in
backend/.env (an Azure "Speech" resource; the free F0 tier covers 0.5
million characters a month -- all 135 videos are about 120,000).

    python -m scripts.topic_videos.voice --voice en-ZA-LeahNeural --only "Exponents"
    python -m scripts.topic_videos.voice --voice en-ZA-LukeNeural        # every topic

Writes media/topic-videos/voice/<voice>/<video-slug>/NN.mp3, one per
scene, with NN.txt holding the words used. A line whose words haven't
changed isn't sent again, so re-running after an edit costs only the
changed lines. Then render with:  python -m scripts.topic_videos.render --voice <voice>
"""

import argparse
import time
from xml.sax.saxutils import escape

import httpx

from app.core.config import settings
from scripts.topic_videos.content import CONTENT
from scripts.topic_videos.narration import narration
from scripts.topic_videos.render import OUT, video_slug

# How the voice should say the brand: "THUTOra" reads as a word it doesn't
# know. Listen to the sample and change the alias if it's not right.
BRAND_ALIAS = "Too-toh-rah"
RATE = "-6%"  # a touch slower than normal: learners are listening and reading


def ssml(text: str, voice: str) -> str:
    lang = "-".join(voice.split("-")[:2])
    body = escape(text).replace("THUTOra", f'<sub alias="{BRAND_ALIAS}">THUTOra</sub>')
    return (f"<speak version='1.0' xml:lang='{lang}'><voice name='{voice}'>"
            f"<prosody rate='{RATE}'>{body}</prosody></voice></speak>")


def synth(client: httpx.Client, text: str, voice: str) -> bytes:
    url = f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "thutora-topic-videos",
    }
    for attempt in range(5):
        r = client.post(url, headers=headers, content=ssml(text, voice).encode("utf-8"))
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (attempt + 1))  # free tier: a few requests a second
            continue
        if r.status_code == 401:
            raise SystemExit("Azure refused the key (401). Check AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in backend/.env.")
        r.raise_for_status()
        return r.content
    raise SystemExit(f"Azure kept refusing (HTTP {r.status_code}). Try again in a minute.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-ZA-LeahNeural")
    ap.add_argument("--only", help="just this topic name")
    a = ap.parse_args()
    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise SystemExit("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in backend/.env first (see docs/ADR-049).")
    made = kept = chars = 0
    with httpx.Client(timeout=60) as client:
        for (subject, grade), topics in CONTENT.items():
            for topic, c in topics.items():
                if a.only and topic != a.only:
                    continue
                folder = OUT / "voice" / a.voice / video_slug(subject, grade, topic)
                folder.mkdir(parents=True, exist_ok=True)
                for i, line in enumerate(narration(subject, grade, topic, c)):
                    mp3, txt = folder / f"{i:02d}.mp3", folder / f"{i:02d}.txt"
                    if mp3.exists() and txt.exists() and txt.read_text(encoding="utf-8") == line:
                        kept += 1
                        continue
                    mp3.write_bytes(synth(client, line, a.voice))
                    txt.write_text(line, encoding="utf-8")
                    made += 1
                    chars += len(line)
                print(f"  {topic}: done")
    print(f"{made} lines voiced ({chars:,} characters), {kept} unchanged. Audio in {OUT / 'voice' / a.voice}")


if __name__ == "__main__":
    main()
