"""
Makes the narration audio for the topic videos (ADR-049) with an Azure
neural voice. Runs on a machine that can reach Azure (your laptop), not in
the build sandbox. Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in
backend/.env (an Azure "Speech" resource; the free F0 tier covers 0.5
million characters a month -- all 135 videos are about 120,000).

    python -m scripts.topic_videos.voice --voice en-ZA-LeahNeural --only "Exponents"
    python -m scripts.topic_videos.voice --voice en-ZA-LukeNeural        # every topic
    python -m scripts.topic_videos.voice --engine windows                # built-in Windows voice,
                                                                         # no account (robotic)

Writes media/topic-videos/voice/<voice>/<video-slug>/NN.mp3, one per
scene, with NN.txt holding the words used. A line whose words haven't
changed isn't sent again, so re-running after an edit costs only the
changed lines. Then render with:  python -m scripts.topic_videos.render --voice <voice>
"""

import argparse
import time
from xml.sax.saxutils import escape

from pathlib import Path

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


# --- Windows built-in voice (no account; a stand-in until Azure/Polly) -----
# Uses System.Speech in Windows PowerShell 5.1 (powershell.exe, which every
# Windows has). PowerShell 7 doesn't include System.Speech. The script is
# passed with -EncodedCommand, so no .ps1 file needs to be trusted.
WINDOWS_TTS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo }
$want = $env:THUTORA_TTS_VOICE
if ($want) { $pick = $voices | Where-Object { $_.Name -like "*$want*" } | Select-Object -First 1 }
if (-not $pick) {
  # prefer a female English voice: South African, then British, then any
  $pick = $voices | Where-Object { $_.Gender -eq 'Female' -and $_.Culture.Name -like 'en-*' } |
    Sort-Object { switch ($_.Culture.Name) { 'en-ZA' {0} 'en-GB' {1} default {2} } } | Select-Object -First 1
}
if (-not $pick) { $pick = $voices | Select-Object -First 1 }
$s.SelectVoice($pick.Name)
$s.Rate = -1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($j in (Get-Content -Raw -Encoding UTF8 $env:THUTORA_TTS_JOBS | ConvertFrom-Json)) {
  $s.SetOutputToWaveFile($j.out, $fmt)
  $s.Speak($j.text)
  $s.SetOutputToNull()
}
Write-Output $pick.Name
"""


def windows_say(text: str) -> str:
    """The built-in voice has no SSML alias here: spell the brand as said."""
    return text.replace("THUTOra", BRAND_ALIAS)


def synth_windows(jobs: list[tuple[str, Path]], voice_name: str | None) -> str:
    """Speak each (text, wav path) with the Windows voice; returns the voice used."""
    import base64
    import json
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump([{"text": windows_say(t), "out": str(p.resolve())} for t, p in jobs], f)
        jobs_file = f.name
    env = {**os.environ, "THUTORA_TTS_JOBS": jobs_file, "THUTORA_TTS_VOICE": voice_name or ""}
    encoded = base64.b64encode(WINDOWS_TTS.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                           capture_output=True, text=True, env=env)
    except FileNotFoundError:
        raise SystemExit("powershell.exe not found: the Windows voice only works on Windows.")
    finally:
        os.unlink(jobs_file)
    if r.returncode != 0:
        raise SystemExit("The Windows voice failed:\n" + (r.stderr or r.stdout)[-1500:])
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["azure", "windows"], default="azure",
                    help="azure (natural, needs a key) or windows (built-in, robotic, no account)")
    ap.add_argument("--voice", help="Azure voice name, or a folder name for the Windows voice (default: windows)")
    ap.add_argument("--windows-voice", help="part of a Windows voice name to use, e.g. Zira or Hazel")
    ap.add_argument("--only", help="just this topic name")
    a = ap.parse_args()
    voice = a.voice or ("windows" if a.engine == "windows" else "en-ZA-LeahNeural")
    if a.engine == "azure" and (not settings.azure_speech_key or not settings.azure_speech_region):
        raise SystemExit("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in backend/.env first (see docs/ADR-049),"
                         " or use --engine windows.")
    ext = "wav" if a.engine == "windows" else "mp3"
    made = kept = chars = 0
    used = None
    with httpx.Client(timeout=60) as client:
        for (subject, grade), topics in CONTENT.items():
            for topic, c in topics.items():
                if a.only and topic != a.only:
                    continue
                folder = OUT / "voice" / voice / video_slug(subject, grade, topic)
                folder.mkdir(parents=True, exist_ok=True)
                todo = []
                for i, line in enumerate(narration(subject, grade, topic, c)):
                    audio, txt = folder / f"{i:02d}.{ext}", folder / f"{i:02d}.txt"
                    if audio.exists() and txt.exists() and txt.read_text(encoding="utf-8") == line:
                        kept += 1
                        continue
                    todo.append((line, audio, txt))
                if a.engine == "windows" and todo:
                    used = synth_windows([(line, audio) for line, audio, _ in todo], a.windows_voice)
                for line, audio, txt in todo:
                    if a.engine == "azure":
                        audio.write_bytes(synth(client, line, voice))
                    txt.write_text(line, encoding="utf-8")
                    made += 1
                    chars += len(line)
                print(f"  {topic}: done")
    if used:
        print(f"Windows voice used: {used}")
    print(f"{made} lines voiced ({chars:,} characters), {kept} unchanged. Audio in {OUT / 'voice' / voice}")


if __name__ == "__main__":
    main()
