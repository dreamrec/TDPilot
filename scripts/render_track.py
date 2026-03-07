#!/usr/bin/env python3
"""Export TD frames for a track and mux with audio via ffmpeg.

Designed for projects like your current scene where per-frame image export is
more reliable than direct movie recording from Movie File Out TOP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from td_mcp.td_client import TDClient


@dataclass
class RenderConfig:
    td_host: str
    td_port: int
    fps: int
    start_frame: int
    end_frame: int
    chunk_size: int
    output_dir: Path
    output_name: str
    frames_dir: Path
    movie_node: str
    track_node: str
    audio_file: Path
    clean_frames: bool
    skip_ffmpeg: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render TD track to MP4 using frame export + ffmpeg.")
    parser.add_argument("--td-host", default="127.0.0.1")
    parser.add_argument("--td-port", type=int, default=9981)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--start-frame", type=int, default=1)
    parser.add_argument("--end-frame", type=int, default=0, help="0 = auto from audio duration")
    parser.add_argument("--chunk-size", type=int, default=120)
    parser.add_argument("--output-dir", default="", help="Default: <project_folder>/renders")
    parser.add_argument("--output-name", default="mountains_breath_v1.mp4")
    parser.add_argument("--frames-subdir", default="frames_mountains_breath_v1")
    parser.add_argument("--movie-node", default="/project1/moviefileout_final")
    parser.add_argument("--track-node", default="/project1/HUH_")
    parser.add_argument("--audio-file", default="", help="Default: from track node file parameter")
    parser.add_argument("--clean-frames", action="store_true")
    parser.add_argument("--skip-ffmpeg", action="store_true")
    return parser.parse_args()


def wav_duration_seconds(path: Path) -> float:
    import contextlib
    import wave

    with contextlib.closing(wave.open(str(path), "rb")) as handle:
        return handle.getnframes() / float(handle.getframerate())


async def ensure_movie_node(client: TDClient, movie_node: str) -> None:
    try:
        await client.request("node/detail", {"path": movie_node})
        return
    except Exception:
        pass

    await client.request(
        "node/copy",
        {
            "source_path": "/project1/moviefileout1",
            "dest_parent": "/project1",
            "new_name": Path(movie_node).name,
        },
    )

    # Ensure final render is connected.
    try:
        await client.request(
            "node/connect",
            {
                "source_path": "/project1/final_render_9x16",
                "target_path": movie_node,
                "source_index": 0,
                "target_index": 0,
            },
        )
    except Exception:
        pass


async def determine_config(args: argparse.Namespace) -> RenderConfig:
    client = TDClient(host=args.td_host, port=args.td_port)
    try:
        info = await client.request("info")
        await ensure_movie_node(client, args.movie_node)

        project_folder = Path(info.get("project_folder") or ".").resolve()
        output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (project_folder / "renders")
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = output_dir / args.frames_subdir
        if args.clean_frames and frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)

        if args.audio_file:
            audio_file = Path(args.audio_file).expanduser().resolve()
        else:
            track_params = await client.request("node/params", {"path": args.track_node, "names": ["file"]})
            audio_path = ((track_params.get("parameters") or {}).get("file") or {}).get("value")
            if not audio_path:
                raise RuntimeError("Could not resolve audio file; pass --audio-file.")
            audio_file = Path(audio_path).expanduser().resolve()

        if not audio_file.exists():
            raise RuntimeError(f"Audio file not found: {audio_file}")

        end_frame = int(args.end_frame)
        if end_frame <= 0:
            duration = wav_duration_seconds(audio_file)
            end_frame = int(math.ceil(duration * args.fps))

        cfg = RenderConfig(
            td_host=args.td_host,
            td_port=args.td_port,
            fps=int(args.fps),
            start_frame=int(args.start_frame),
            end_frame=end_frame,
            chunk_size=max(1, int(args.chunk_size)),
            output_dir=output_dir,
            output_name=args.output_name,
            frames_dir=frames_dir,
            movie_node=args.movie_node,
            track_node=args.track_node,
            audio_file=audio_file,
            clean_frames=bool(args.clean_frames),
            skip_ffmpeg=bool(args.skip_ffmpeg),
        )
        return cfg
    finally:
        await client.close()


def _chunk_ranges(start_frame: int, end_frame: int, size: int):
    f = start_frame
    while f <= end_frame:
        end = min(f + size - 1, end_frame)
        yield f, end
        f = end + 1


async def export_frames(cfg: RenderConfig) -> None:
    client = TDClient(host=cfg.td_host, port=cfg.td_port, timeout=30.0)
    try:
        prep_code = f"""
t = (op('/project1') or op('/')).time
m = op({cfg.movie_node!r})
t.play = False
t.start = {cfg.start_frame}
t.end = {cfg.end_frame}
t.frame = {cfg.start_frame}
m.par.type = 'image'
m.par.imagefiletype = 'jpeg'
m.par.record = False
__result__ = {{'start': int(t.start), 'end': int(t.end), 'frame': float(t.frame)}}
"""
        await client.request("exec", {"code": prep_code, "exec_mode": "full"})

        total = cfg.end_frame - cfg.start_frame + 1
        done = 0
        for c_start, c_end in _chunk_ranges(cfg.start_frame, cfg.end_frame, cfg.chunk_size):
            code = f"""
t = (op('/project1') or op('/')).time
m = op({cfg.movie_node!r})
out = {str(cfg.frames_dir)!r}
for f in range({c_start}, {c_end + 1}):
    t.frame = f
    p = out + '/frame_%05d.jpg' % f
    m.par.file = p
    m.cook(force=True)
    m.par.addframe.pulse()
__result__ = {{'chunk_start': {c_start}, 'chunk_end': {c_end}}}
"""
            await client.request("exec", {"code": code, "exec_mode": "full"})
            done += (c_end - c_start + 1)
            print(f"[render] frames {c_start}-{c_end} ({done}/{total})")
            sys.stdout.flush()
    finally:
        await client.close()


def run_ffmpeg(cfg: RenderConfig) -> Path:
    output_file = cfg.output_dir / cfg.output_name
    frame_pattern = str(cfg.frames_dir / "frame_%05d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(cfg.fps),
        "-start_number",
        str(cfg.start_frame),
        "-i",
        frame_pattern,
        "-i",
        str(cfg.audio_file),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(cfg.fps),
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-shortest",
        str(output_file),
    ]
    print("[render] ffmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_file


async def async_main() -> int:
    args = parse_args()
    cfg = await determine_config(args)

    print(
        json.dumps(
            {
                "td": f"{cfg.td_host}:{cfg.td_port}",
                "fps": cfg.fps,
                "start_frame": cfg.start_frame,
                "end_frame": cfg.end_frame,
                "frame_count": cfg.end_frame - cfg.start_frame + 1,
                "frames_dir": str(cfg.frames_dir),
                "audio_file": str(cfg.audio_file),
                "output_file": str(cfg.output_dir / cfg.output_name),
            },
            indent=2,
        )
    )

    await export_frames(cfg)

    if cfg.skip_ffmpeg:
        print("[render] skipped ffmpeg mux (--skip-ffmpeg)")
        return 0

    out = run_ffmpeg(cfg)
    size = out.stat().st_size if out.exists() else 0
    print(json.dumps({"output_file": str(out), "size_bytes": size}, indent=2))
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("[render] interrupted")
        return 130
    except Exception as exc:
        print(f"[render] error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
