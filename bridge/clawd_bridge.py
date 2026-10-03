#!/usr/bin/env python3
"""Clawd bridge — the PC half of the desk buddy.

One process owns the board's serial port and does three jobs:

1. **Mirror Claude Code.** Claude Code hooks POST their JSON to
   http://127.0.0.1:8765/hook; each one becomes a mood + captions on the eyes.
2. **Voice in.** While the buddy's button is held the board streams 16 kHz mic
   audio; on release it is transcribed (OpenAI) and sent to a dedicated Claude
   Code session (`claude -p --resume <id>`) in --workdir.
3. **Voice out.** Claude's reply is synthesised (OpenAI TTS), resampled to
   16 kHz mono, and streamed to the speaker in real time.

Pressing the knob cancels whatever is happening (speech or a running prompt).

    python clawd_bridge.py run --workdir ~/dev/myproject
    python clawd_bridge.py install-hooks        # once
    python clawd_bridge.py demo                 # cycle every mood, no Claude
    python clawd_bridge.py say "hello there"    # TTS smoke test
"""

from __future__ import annotations

import argparse
import array
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from atech import Board

HOOK_PORT = 8765
HOOK_URL = f"http://127.0.0.1:{HOOK_PORT}/hook"
HOOK_COMMAND = (
    f"curl -s -m 1 -X POST -H 'Content-Type: application/json' "
    f"--data-binary @- {HOOK_URL} >/dev/null 2>&1 || true"
)
HOOK_EVENTS = [
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "Notification", "Stop", "SessionEnd",
]
STATE_FILE = Path.home() / ".config" / "clawd_bot" / "state.json"

MIC_RATE = 16000
CHUNK_SAMPLES = 512                    # 32 ms per play_pcm line
LEAD_S = 0.15                          # how far ahead of real time we send

SPOKEN_STYLE = (
    "You are being driven by voice through a small desk robot called Clawd. "
    "Your final message is read aloud through a tiny speaker. Do the work as "
    "usual, then end with a reply of at most two short spoken sentences: plain "
    "English, no markdown, no code, no lists, no file paths unless essential."
)


def clean(text: str, n: int = 26) -> str:
    """Make text safe for the firmware's tiny parser: ASCII, no quotes/backslashes."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.encode("ascii", "replace").decode().replace('"', "'").replace("\\", "/")
    return text if len(text) <= n else text[: n - 1] + "~"


def tool_detail(name: str, inp: dict) -> str:
    if not isinstance(inp, dict):
        return ""
    for key in ("command", "description", "pattern", "url", "query", "prompt"):
        if inp.get(key):
            return str(inp[key])
    if inp.get("file_path"):
        return Path(str(inp["file_path"])).name
    return ""


def resample_24k_to_16k(pcm: bytes) -> bytes:
    """Linear 3:2 resample of s16le mono. Pure Python; fine for a few seconds."""
    src = array.array("h")
    src.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder != "little":
        src.byteswap()
    out = array.array("h")
    n = len(src)
    pos = 0.0
    while pos < n - 1:
        i = int(pos)
        f = pos - i
        out.append(int(src[i] * (1 - f) + src[i + 1] * f))
        pos += 1.5
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


class Bridge:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.board: Board | None = None
        self.tx_lock = threading.Lock()
        self.voice_busy = threading.Event()     # listening / thinking-by-voice / speaking
        self.cancel = threading.Event()
        self.audio = bytearray()
        self.capturing = False
        self.claude_proc: subprocess.Popen | None = None
        self._openai = None

    # ------------------------------------------------------------ board I/O
    def send(self, key: str, value: str = "") -> None:
        board = self.board
        if board is None:
            return
        try:
            with self.tx_lock:
                board.send(key, value)
        except Exception as exc:                # unplugged mid-send
            print(f"[bridge] send failed: {exc}", file=sys.stderr)
            self.board = None                   # connect_loop reconnects
            try:
                board.close()
            except Exception:
                pass

    def show(self, mood: str, label: str | None = None, detail: str | None = None) -> None:
        if label is not None:
            self.send("label", clean(label))
        if detail is not None:
            self.send("detail", clean(detail))
        self.send("mood", mood)

    def connect_loop(self) -> None:
        while True:
            if self.board is None:
                try:
                    # A replugged ESP32 often comes back as ttyACM1 instead of
                    # ttyACM0, so a pinned port that vanished falls back to auto.
                    port = self.args.port
                    if port and not Path(port).exists():
                        port = None
                    self.board = Board.connect(port=port)
                    print("[bridge] board connected")
                    time.sleep(1.0)
                    self.show("idle", "hi!", Path(self.args.workdir).name)
                    threading.Thread(target=self.event_loop, args=(self.board,), daemon=True).start()
                except Exception as exc:
                    print(f"[bridge] waiting for board: {exc}")
            time.sleep(3.0)

    def event_loop(self, board: Board) -> None:
        for ev in board.events():
            if board is not self.board:
                return
            if ev.key == "btn" and ev.value == 1:
                self.on_ptt_start()
            elif ev.key == "mic_audio" and self.capturing:
                try:
                    self.audio.extend(base64.b64decode(ev.value))
                except Exception:
                    pass
            elif ev.key == "ptt" and ev.value == "end":
                self.capturing = False
                audio, self.audio = bytes(self.audio), bytearray()
                threading.Thread(target=self.voice_turn, args=(audio,), daemon=True).start()
            elif ev.key == "knob_btn":
                self.on_cancel()
            elif ev.key == "volume":
                print(f"[bridge] volume {ev.value}%")

    # ------------------------------------------------------------ hooks
    def on_hook(self, data: dict) -> None:
        event = data.get("hook_event_name", "")
        if self.voice_busy.is_set() and event not in ("PreToolUse", "PostToolUse", "Notification"):
            return                               # voice turn owns the face
        if event == "SessionStart":
            self.show("idle", "ready", Path(data.get("cwd", "")).name)
        elif event == "UserPromptSubmit":
            self.show("thinking", "thinking", data.get("prompt", ""))
        elif event == "PreToolUse":
            name = data.get("tool_name", "tool")
            self.show("tool", name, tool_detail(name, data.get("tool_input", {})))
        elif event == "PostToolUse":
            self.show("thinking", "thinking", "")
        elif event == "Notification":
            self.show("waiting", "needs you", data.get("message", ""))
        elif event == "Stop":
            self.show("done", "done", "")
        elif event == "SessionEnd":
            self.show("idle", "", "")

    # ------------------------------------------------------------ voice
    @property
    def openai(self):
        if self._openai is None:
            from openai import OpenAI          # imported lazily: hooks work without it
            self._openai = OpenAI()
        return self._openai

    def on_ptt_start(self) -> None:
        self.on_cancel(quiet=True)
        self.voice_busy.set()
        self.cancel.clear()
        self.audio = bytearray()
        self.capturing = True

    def on_cancel(self, quiet: bool = False) -> None:
        self.cancel.set()
        proc = self.claude_proc
        if proc and proc.poll() is None:
            proc.terminate()
        self.send("spk_stop")
        if not quiet:
            self.voice_busy.clear()
            self.show("idle", "cancelled", "")

    def voice_turn(self, audio: bytes) -> None:
        try:
            seconds = len(audio) / 2 / MIC_RATE
            if seconds < 0.4:
                self.show("idle", "too short", "hold the button")
                return
            self.show("thinking", "transcribing", f"{seconds:.1f}s of audio")
            text = self.transcribe(audio)
            print(f"[bridge] heard: {text!r}")
            if not text.strip():
                self.show("idle", "didn't catch", "that - try again")
                return
            if self.cancel.is_set():
                return
            self.show("thinking", "you said", text)
            reply = self.ask_claude(text)
            if self.cancel.is_set():
                return
            if not reply:
                self.show("error", "claude failed", "see bridge log")
                return
            print(f"[bridge] reply: {reply!r}")
            self.speak(reply)
        except Exception as exc:
            print(f"[bridge] voice turn failed: {exc}", file=sys.stderr)
            self.show("error", "error", str(exc))
        finally:
            self.voice_busy.clear()

    def transcribe(self, pcm: bytes) -> str:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(MIC_RATE)
            w.writeframes(pcm)
        buf.name = "speech.wav"
        buf.seek(0)
        if self.args.save_audio:
            Path(self.args.save_audio).write_bytes(buf.getvalue())
        result = self.openai.audio.transcriptions.create(model=self.args.stt_model, file=buf)
        return result.text

    def ask_claude(self, text: str) -> str:
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        workdir = str(Path(self.args.workdir).expanduser().resolve())
        cmd = [
            self.args.claude_bin, "-p", text,
            "--output-format", "json",
            "--append-system-prompt", SPOKEN_STYLE,
            "--permission-mode", self.args.permission_mode,
        ]
        session = state.get(workdir)
        if session and not self.args.new_session:
            cmd += ["--resume", session]
        self.claude_proc = subprocess.Popen(
            cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        out, err = self.claude_proc.communicate()
        if self.claude_proc.returncode != 0 and not out.strip():
            print(f"[bridge] claude exited {self.claude_proc.returncode}: {err.strip()}", file=sys.stderr)
            if session:                         # stale session id: start fresh next time
                state.pop(workdir, None)
                STATE_FILE.write_text(json.dumps(state, indent=2))
            return ""
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return out.strip()
        if data.get("session_id"):
            state[workdir] = data["session_id"]
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, indent=2))
        return str(data.get("result", "")).strip()

    def speak(self, text: str) -> None:
        text = text[: self.args.max_speech_chars]
        self.show("speaking", "", "")
        resp = self.openai.audio.speech.create(
            model=self.args.tts_model,
            voice=self.args.voice,
            input=text,
            response_format="pcm",              # 24 kHz s16le mono
        )
        pcm = resample_24k_to_16k(resp.content)
        step = CHUNK_SAMPLES * 2
        start = time.monotonic()
        for i, off in enumerate(range(0, len(pcm), step)):
            if self.cancel.is_set() or self.board is None:
                return
            due = start + i * CHUNK_SAMPLES / MIC_RATE - LEAD_S
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.send("spk_play_pcm", base64.b64encode(pcm[off: off + step]).decode())
        time.sleep(LEAD_S + 0.2)
        self.show("idle", "", "")

    # ------------------------------------------------------------ main
    def serve_hooks(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):                  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.send_response(204)
                self.end_headers()
                try:
                    bridge.on_hook(json.loads(body or b"{}"))
                except Exception as exc:
                    print(f"[bridge] bad hook payload: {exc}", file=sys.stderr)

            def log_message(self, *a):          # keep the console quiet
                pass

        server = ThreadingHTTPServer(("127.0.0.1", HOOK_PORT), Handler)
        print(f"[bridge] listening for Claude Code hooks on {HOOK_URL}")
        server.serve_forever()

    def run(self) -> None:
        threading.Thread(target=self.serve_hooks, daemon=True).start()
        self.connect_loop()


# ---------------------------------------------------------------- commands
def cmd_install_hooks(args: argparse.Namespace) -> None:
    path = Path(args.settings).expanduser()
    settings = json.loads(path.read_text()) if path.exists() else {}
    if path.exists():
        backup = path.with_suffix(".json.clawd-backup")
        shutil.copy(path, backup)
        print(f"backed up {path} -> {backup}")
    hooks = settings.setdefault("hooks", {})
    added = 0
    for event in HOOK_EVENTS:
        groups = hooks.setdefault(event, [])
        if any(h.get("command") == HOOK_COMMAND for g in groups for h in g.get("hooks", [])):
            continue
        group = {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 2}]}
        if event in ("PreToolUse", "PostToolUse"):
            group["matcher"] = "*"
        groups.append(group)
        added += 1
    path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"added Clawd hook to {added} event(s) in {path}")


def cmd_uninstall_hooks(args: argparse.Namespace) -> None:
    path = Path(args.settings).expanduser()
    settings = json.loads(path.read_text())
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        groups = [
            g for g in hooks[event]
            if not any(h.get("command") == HOOK_COMMAND for h in g.get("hooks", []))
        ]
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"removed Clawd hooks from {path}")


def cmd_demo(args: argparse.Namespace) -> None:
    steps = [
        ("idle", "hi!", "demo mode"), ("thinking", "thinking", "refactor auth"),
        ("tool", "Bash", "npm test"), ("tool", "Edit", "auth.ts"),
        ("waiting", "needs you", "allow Bash: rm -rf dist"), ("done", "done", ""),
        ("listening", "listening", ""), ("speaking", "", ""),
        ("error", "error", "demo error"), ("sleep", "", ""), ("idle", "", ""),
    ]
    with Board.connect(port=args.port) as board:
        time.sleep(1.0)
        for mood, label, detail in steps:
            print(f"-> {mood}")
            board.send("label", clean(label))
            board.send("detail", clean(detail))
            board.send("mood", mood)
            time.sleep(args.hold)


def cmd_say(args: argparse.Namespace) -> None:
    bridge = Bridge(args)
    bridge.board = Board.connect(port=args.port)
    time.sleep(1.0)
    bridge.speak(" ".join(args.text))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port (default: auto-detect)")
    ap.add_argument("--tts-model", default="gpt-4o-mini-tts")
    ap.add_argument("--voice", default="sage")
    ap.add_argument("--max-speech-chars", type=int, default=600)
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run the bridge")
    run.add_argument("--workdir", default=".", help="project dir voice prompts run in")
    run.add_argument("--stt-model", default="gpt-4o-mini-transcribe")
    run.add_argument("--claude-bin", default=shutil.which("claude") or str(Path.home() / ".local/bin/claude"))
    run.add_argument("--permission-mode", default="acceptEdits",
                     choices=["default", "acceptEdits", "plan", "bypassPermissions"],
                     help="permission mode for voice-driven prompts (default: acceptEdits)")
    run.add_argument("--new-session", action="store_true", help="don't resume the saved voice session")
    run.add_argument("--save-audio", help="also write each utterance to this .wav (debugging)")

    for name in ("install-hooks", "uninstall-hooks"):
        p = sub.add_parser(name, help=f"{name.split('-')[0]} Claude Code hooks")
        p.add_argument("--settings", default="~/.claude/settings.json")

    demo = sub.add_parser("demo", help="cycle every mood without Claude")
    demo.add_argument("--hold", type=float, default=4.0)

    say = sub.add_parser("say", help="speak text through the buddy")
    say.add_argument("text", nargs="+")

    args = ap.parse_args()
    if args.cmd == "run":
        if not os.environ.get("OPENAI_API_KEY"):
            print("[bridge] OPENAI_API_KEY not set: hooks will work, voice will not", file=sys.stderr)
        Bridge(args).run()
    elif args.cmd == "install-hooks":
        cmd_install_hooks(args)
    elif args.cmd == "uninstall-hooks":
        cmd_uninstall_hooks(args)
    elif args.cmd == "demo":
        cmd_demo(args)
    elif args.cmd == "say":
        cmd_say(args)


if __name__ == "__main__":
    main()
