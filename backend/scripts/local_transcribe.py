import argparse
import json
import sys

from faster_whisper import WhisperModel


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--model-size", default="tiny")
    parser.add_argument("--language", default="zh")
    return parser.parse_args()


def main():
    args = parse_args()
    model = WhisperModel(args.model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(args.audio_path, language=args.language, vad_filter=True)
    text = "".join(segment.text for segment in segments).strip()
    json.dump({"text": text}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
