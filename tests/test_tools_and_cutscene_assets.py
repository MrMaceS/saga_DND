import wave
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def test_pcm_to_wav_makes_a_valid_file(tmp_path):
    from generate_voice import pcm_to_wav
    pcm = (b"\x00\x01" * 2400)           # 0.1 с при 24 кГц, 16 бит, моно
    out = tmp_path / "a.wav"
    pcm_to_wav(pcm, out)
    with wave.open(str(out)) as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) == (1, 2, 24000, 2400)


def test_cutscene_text_joins_subtitles():
    from generate_voice import cutscene_text
    assert cutscene_text({"subtitles": [{"text": "Раз."}, {"text": "Два."}]}) == "Раз. Два."


def test_cutscene_payload_picks_up_media_by_name(tmp_path, monkeypatch):
    from app.engine import content
    monkeypatch.setattr(content, "ASSETS_DIR", tmp_path)
    cs = content.cutscene_payload("cs_third_strike")
    assert cs["audio_url"] is None and cs["still_url"] is None and cs["video_url"] is None and cs["subtitles"]
    (tmp_path / "audio/cutscenes").mkdir(parents=True)
    (tmp_path / "audio/cutscenes/cs_third_strike.wav").write_bytes(b"x")
    (tmp_path / "cutscenes/stills").mkdir(parents=True)
    (tmp_path / "cutscenes/stills/cs_third_strike.webp").write_bytes(b"x")
    (tmp_path / "cutscenes/video").mkdir(parents=True)
    (tmp_path / "cutscenes/video/cs_third_strike.mp4").write_bytes(b"x")
    cs = content.cutscene_payload("cs_third_strike")
    assert cs["audio_url"] == "/assets/audio/cutscenes/cs_third_strike.wav"
    assert cs["still_url"].endswith("cs_third_strike.webp") and cs["video_url"].endswith("cs_third_strike.mp4")
