#!/usr/bin/env python3
"""Video Downloader GUI - Tkinter dark theme. Manual single-link only."""
from __future__ import annotations
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import (
    Tk, Text, StringVar, Entry, END, DISABLED, NORMAL,
    messagebox, OptionMenu, Canvas, Scrollbar,
)
import tkinter as tk

import downloader as dl

BASE_DIR = Path.home() / "VideoDownloader"
LOG_FILE = BASE_DIR / "logs" / "downloader.log"

BG = "#1a1a1a"
FG = "#ffffff"
ACCENT = "#00ff88"
PANEL = "#222222"
MUTED = "#888888"

MP4_QUALITIES = ["720p", "1080p", "1440p", "2160p", "best"]
MP3_BITRATES = ["128", "192", "256", "320"]


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.download_proc: subprocess.Popen | None = None

        root.title("Video Downloader")
        root.configure(bg=BG)
        root.geometry("780x560")

        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True)
        self.canvas = Canvas(outer, bg=BG, highlightthickness=0, borderwidth=0)
        vbar = Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(self.canvas, bg=BG)
        self._content_window = self.canvas.create_window((0, 0), window=content, anchor="nw")

        def _on_configure(_e=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.itemconfigure(self._content_window, width=self.canvas.winfo_width())
        content.bind("<Configure>", _on_configure)
        self.canvas.bind("<Configure>", _on_configure)

        def _on_wheel(event):
            delta = -1 * (event.delta // 120) if abs(event.delta) >= 120 else -1 * event.delta
            self.canvas.yview_scroll(delta, "units")
        self.canvas.bind_all("<MouseWheel>", _on_wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

        tk.Label(content, text="Video Downloader", bg=BG, fg=ACCENT,
                 font=("Helvetica", 22, "bold")).pack(pady=(16, 4))

        self.status_var = StringVar(value="Status: Idle")
        tk.Label(content, textvariable=self.status_var, bg=BG, fg=FG,
                 font=("Helvetica", 12)).pack(pady=(0, 10))

        btn_frame = tk.Frame(content, bg=BG)
        btn_frame.pack(pady=6)
        self._mkbtn(btn_frame, "📁 Open Folder", self.open_folder).grid(row=0, column=0, padx=4)

        quick_frame = tk.Frame(content, bg=BG)
        quick_frame.pack(fill="x", padx=20, pady=(16, 0))
        self._build_quick(quick_frame)

        tk.Label(content, text="Recent log", bg=BG, fg=FG,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        self.log_view = Text(content, height=10, bg=PANEL, fg=FG, insertbackground=FG,
                             relief="flat", font=("Menlo", 10), wrap="none")
        self.log_view.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.log_view.configure(state=DISABLED)

        self._refresh_log()
        self._tick()

    def _mkbtn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=PANEL, fg=ACCENT,
                         activebackground=ACCENT, activeforeground=BG,
                         relief="flat", padx=14, pady=8,
                         font=("Helvetica", 11, "bold"),
                         highlightthickness=0, borderwidth=0)

    def _build_quick(self, parent) -> None:
        tk.Label(parent, text="⚡ Quick download (paste a single link)",
                 bg=BG, fg=ACCENT, font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(parent, text="Saves to ~/VideoDownloader/mp4, /mp3, or /pinterest_single",
                 bg=BG, fg=MUTED, font=("Helvetica", 9)).pack(anchor="w", pady=(0, 6))

        self.quick_status = StringVar(value="")
        self.mp4_quality_var = StringVar(value="1080p")
        self.mp3_bitrate_var = StringVar(value="192")

        def style_menu(menu):
            menu.configure(bg=PANEL, fg=ACCENT, activebackground=ACCENT,
                           activeforeground=BG, relief="flat",
                           highlightthickness=0, font=("Helvetica", 10, "bold"),
                           width=6)
            menu["menu"].configure(bg=PANEL, fg=FG)

        def make_row(label_text, hint, action_label, action, quality_var=None,
                     quality_choices=None, quality_suffix=""):
            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label_text, bg=BG, fg=FG, width=18, anchor="w",
                     font=("Helvetica", 10, "bold")).pack(side="left")
            entry = Entry(row, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                          font=("Menlo", 10))
            entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
            if quality_var is not None:
                m = OptionMenu(row, quality_var, *quality_choices)
                style_menu(m)
                m.pack(side="left", padx=(0, 6))
                if quality_suffix:
                    tk.Label(row, text=quality_suffix, bg=BG, fg=MUTED,
                             font=("Helvetica", 9)).pack(side="left", padx=(0, 6))
            btn = tk.Button(
                row, text=action_label, bg=PANEL, fg=ACCENT,
                activebackground=ACCENT, activeforeground=BG, relief="flat",
                padx=12, pady=4, font=("Helvetica", 10, "bold"),
                highlightthickness=0, borderwidth=0,
                command=lambda: action(entry),
            )
            btn.pack(side="left")
            entry.bind("<Return>", lambda _e: action(entry))
            tk.Label(parent, text=hint, bg=BG, fg=MUTED,
                     font=("Helvetica", 9)).pack(anchor="w", padx=(126, 0), pady=(0, 4))

        make_row("⬇ YouTube → MP4:",
                 "Video as MP4 → ~/VideoDownloader/mp4/",
                 "⬇ Download MP4", self._quick_youtube_mp4,
                 quality_var=self.mp4_quality_var,
                 quality_choices=MP4_QUALITIES)

        make_row("⬇ YouTube → MP3:",
                 "Audio only → ~/VideoDownloader/mp3/",
                 "⬇ Download MP3", self._quick_youtube_mp3,
                 quality_var=self.mp3_bitrate_var,
                 quality_choices=MP3_BITRATES,
                 quality_suffix="kbps")

        make_row("⬇ Pinterest single:",
                 "Pin URL — video or image. Saves to ~/VideoDownloader/pinterest_single/",
                 "⬇ Download", self._quick_pinterest)

        tk.Label(parent, textvariable=self.quick_status, bg=BG, fg=ACCENT,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(2, 0))

    def _run_quick(self, fn, label: str, entry: Entry, *args) -> None:
        url = entry.get().strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showwarning("Invalid URL", "Paste a full http(s) link.")
            return
        self.quick_status.set(f"⏳ {label}: downloading…")

        def worker():
            try:
                ok = fn(url, *args)
                if ok:
                    self.quick_status.set(f"✓ {label}: done")
                    self.root.after(0, lambda: entry.delete(0, END))
                else:
                    self.quick_status.set(f"✗ {label}: failed (see log)")
            except Exception as e:
                self.quick_status.set(f"✗ {label}: {e}")
            finally:
                self._refresh_log()

        threading.Thread(target=worker, daemon=True).start()

    def _quick_youtube_mp4(self, entry: Entry) -> None:
        self._run_quick(dl.download_youtube_mp4, "YouTube MP4", entry,
                        self.mp4_quality_var.get())

    def _quick_youtube_mp3(self, entry: Entry) -> None:
        self._run_quick(dl.download_youtube_mp3, "YouTube MP3", entry,
                        self.mp3_bitrate_var.get())

    def _quick_pinterest(self, entry: Entry) -> None:
        self._run_quick(dl.download_pinterest_single, "Pinterest", entry)

    def _refresh_log(self) -> None:
        lines: list[str] = []
        if LOG_FILE.exists():
            try:
                with LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()[-20:]
            except Exception as e:
                lines = [f"(failed to read log: {e})"]
        else:
            lines = ["(no log yet — run a download)"]
        self.log_view.configure(state=NORMAL)
        self.log_view.delete("1.0", END)
        self.log_view.insert(END, "".join(lines))
        self.log_view.see(END)
        self.log_view.configure(state=DISABLED)

    def _tick(self) -> None:
        self._refresh_log()
        self.root.after(5000, self._tick)

    def open_folder(self) -> None:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["open", str(BASE_DIR)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(BASE_DIR)], check=False)
        else:
            subprocess.run(["xdg-open", str(BASE_DIR)], check=False)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
