"""Озвучка кат-сцен через Gemini TTS. Запуск: GEMINI_API_KEY=... python tools/generate_voice.py [--voice Algenib] [--only cs_prologue]

Читает data/cutscenes.json, сохраняет assets/audio/cutscenes/{id}.mp3 (если есть ffmpeg) или .wav.
Идентификатор модели TTS проверьте в документации Gemini API и при необходимости задайте --model.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STYLE = ("Read as a dark Norse saga narrator: a low, slow, slightly gravelly male voice, restrained and ominous, "
                 "never theatrical. Pause briefly after each sentence. Speak in Russian:")


def pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000) -> None:
    """Gemini TTS отдаёт сырые 16-битные моно-отсчёты 24 кГц: оборачиваем их в WAV."""
    with wave.open(str(path), "wb") as f:
        f.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        f.writeframes(pcm)


def cutscene_text(cs: dict) -> str:
    return " ".join(line["text"] for line in cs["subtitles"])


def synthesize(client, model: str, voice: str, style: str, text: str) -> bytes:
    from google.genai import types
    response = client.models.generate_content(
        model=model, contents=f"{style}\n\n{text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
    return response.candidates[0].content.parts[0].inline_data.data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Algenib")
    ap.add_argument("--model", default=os.environ.get("MODEL_TTS", "gemini-2.5-flash-preview-tts"))
    ap.add_argument("--style", default=DEFAULT_STYLE)
    ap.add_argument("--only", nargs="*", help="только эти id кат-сцен")
    ap.add_argument("--force", action="store_true", help="перезаписать существующие файлы")
    args = ap.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        print("Задайте GEMINI_API_KEY"); return 1
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    out_dir = ROOT / "assets" / "audio" / "cutscenes"
    out_dir.mkdir(parents=True, exist_ok=True)
    cutscenes = json.loads((ROOT / "data" / "cutscenes.json").read_text(encoding="utf-8"))
    for cid, cs in cutscenes.items():
        if args.only and cid not in args.only:
            continue
        if not args.force and any((out_dir / f"{cid}{ext}").exists() for ext in (".mp3", ".wav", ".ogg")):
            print(f"= {cid}: уже есть"); continue
        pcm = synthesize(client, args.model, args.voice, args.style, cutscene_text(cs))
        wav = out_dir / f"{cid}.wav"
        pcm_to_wav(pcm, wav)
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "3",
                            str(out_dir / f"{cid}.mp3")], check=True)
            wav.unlink()
        print(f"+ {cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
