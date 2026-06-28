import os
import re
import sys
import threading
import queue
import subprocess
import json
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yt_dlp

APP_NAME = "Pullr"
APP_VERSION = "0.1.3"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# NexusBar-inspired theme
COLOR_BG = "#08070D"
COLOR_PANEL = "#11101A"
COLOR_PANEL_2 = "#171428"
COLOR_INPUT = "#0D0B15"
COLOR_BORDER = "#2B2144"
COLOR_PURPLE = "#7C3AED"
COLOR_PURPLE_HOVER = "#9B5CFF"
COLOR_PURPLE_DARK = "#4C1D95"
COLOR_TEXT = "#F4F0FF"
COLOR_MUTED = "#A99BC7"

SAFE_CHARS_RE = re.compile(r'[<>:"/\\|?*]')


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    """Store user settings beside the app/exe for simple portable behavior."""
    return app_base_dir() / "pullr_settings.json"


def load_last_folder() -> str:
    default_folder = str(Path.home() / "Downloads")
    try:
        cfg = config_path()
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            folder = str(data.get("last_folder", "")).strip()
            if folder:
                return folder
    except Exception:
        pass
    return default_folder


def save_last_folder(folder: str) -> None:
    folder = str(folder).strip()
    if not folder:
        return
    try:
        cfg = config_path()
        cfg.write_text(json.dumps({"last_folder": folder}, indent=2), encoding="utf-8")
    except Exception:
        # Saving the convenience setting should never block downloads.
        pass


def bundled_ffmpeg_dir() -> str | None:
    """Use ./ffmpeg/bin if present, otherwise rely on system PATH."""
    base = app_base_dir()
    possible = [
        base / "ffmpeg" / "bin",
        base / "bin",
        base,
    ]
    for p in possible:
        if (p / "ffmpeg.exe").exists() or (p / "ffmpeg").exists():
            return str(p)
    return None


class QueueLogger:
    def __init__(self, ui_queue: queue.Queue):
        self.ui_queue = ui_queue

    def debug(self, msg):
        if msg and not msg.startswith("[debug]"):
            self.ui_queue.put(("log", msg))

    def warning(self, msg):
        self.ui_queue.put(("log", f"Warning: {msg}"))

    def error(self, msg):
        self.ui_queue.put(("error", msg))


class DownloadApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("760x640")
        self.minsize(720, 620)
        self.configure(fg_color=COLOR_BG)

        self.ui_queue = queue.Queue()
        self.download_thread = None
        self.is_downloading = False

        self.url_var = ctk.StringVar()
        self.folder_var = ctk.StringVar(value=load_last_folder())
        self.mode_var = ctk.StringVar(value="Video MP4")
        self.quality_var = ctk.StringVar(value="Best")
        self.playlist_var = ctk.BooleanVar(value=False)

        self.build_ui()
        self.after(100, self.process_queue)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)

        header = ctk.CTkFrame(self, corner_radius=18, fg_color=COLOR_PANEL_2, border_width=1, border_color=COLOR_BORDER)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text=APP_NAME, font=ctk.CTkFont(size=30, weight="bold"), text_color=COLOR_TEXT)
        title.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))

        subtitle = ctk.CTkLabel(
            header,
            text="Paste a video link, choose a format, and save it locally. Only download content you own or have permission to save.",
            text_color=COLOR_MUTED,
            wraplength=690,
            justify="left",
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        link_frame = ctk.CTkFrame(self, corner_radius=14, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_BORDER)
        link_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        link_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(link_frame, text="Link", text_color=COLOR_TEXT).grid(row=0, column=0, padx=(14, 8), pady=14)
        self.url_entry = ctk.CTkEntry(link_frame, textvariable=self.url_var, placeholder_text="https://www.youtube.com/watch?v=...", fg_color=COLOR_INPUT, border_color=COLOR_BORDER, text_color=COLOR_TEXT, placeholder_text_color=COLOR_MUTED)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=14)

        options = ctk.CTkFrame(self, corner_radius=14, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_BORDER)
        options.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        options.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(options, text="Format", text_color=COLOR_TEXT).grid(row=0, column=0, padx=(14, 8), pady=(14, 8), sticky="w")
        self.mode_menu = ctk.CTkOptionMenu(options, variable=self.mode_var, values=["Video MP4", "Audio MP3"], fg_color=COLOR_PURPLE_DARK, button_color=COLOR_PURPLE, button_hover_color=COLOR_PURPLE_HOVER, text_color=COLOR_TEXT, dropdown_fg_color=COLOR_PANEL_2, dropdown_hover_color=COLOR_PURPLE_DARK, dropdown_text_color=COLOR_TEXT)
        self.mode_menu.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(14, 8))

        ctk.CTkLabel(options, text="Quality", text_color=COLOR_TEXT).grid(row=0, column=2, padx=(14, 8), pady=(14, 8), sticky="w")
        self.quality_menu = ctk.CTkOptionMenu(options, variable=self.quality_var, values=["Best", "1080p", "720p", "480p", "360p"], fg_color=COLOR_PURPLE_DARK, button_color=COLOR_PURPLE, button_hover_color=COLOR_PURPLE_HOVER, text_color=COLOR_TEXT, dropdown_fg_color=COLOR_PANEL_2, dropdown_hover_color=COLOR_PURPLE_DARK, dropdown_text_color=COLOR_TEXT)
        self.quality_menu.grid(row=0, column=3, sticky="ew", padx=(0, 14), pady=(14, 8))

        self.playlist_check = ctk.CTkCheckBox(options, text="Allow playlist downloads", variable=self.playlist_var, text_color=COLOR_TEXT, fg_color=COLOR_PURPLE, hover_color=COLOR_PURPLE_HOVER, border_color=COLOR_BORDER, checkmark_color=COLOR_TEXT)
        self.playlist_check.grid(row=1, column=1, columnspan=3, sticky="w", padx=(0, 14), pady=(2, 14))

        folder = ctk.CTkFrame(self, corner_radius=14, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_BORDER)
        folder.grid(row=3, column=0, sticky="ew", padx=18, pady=8)
        folder.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(folder, text="Folder", text_color=COLOR_TEXT).grid(row=0, column=0, padx=(14, 8), pady=14)
        self.folder_entry = ctk.CTkEntry(folder, textvariable=self.folder_var, fg_color=COLOR_INPUT, border_color=COLOR_BORDER, text_color=COLOR_TEXT)
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=14)
        ctk.CTkButton(folder, text="Browse", width=96, command=self.choose_folder, fg_color=COLOR_PURPLE_DARK, hover_color=COLOR_PURPLE_HOVER, text_color=COLOR_TEXT).grid(row=0, column=2, padx=(0, 8), pady=14)
        ctk.CTkButton(folder, text="Open Folder", width=112, command=self.open_folder, fg_color=COLOR_PURPLE, hover_color=COLOR_PURPLE_HOVER, text_color=COLOR_TEXT).grid(row=0, column=3, padx=(0, 14), pady=14)

        actions = ctk.CTkFrame(self, corner_radius=14, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_BORDER)
        actions.grid(row=4, column=0, sticky="ew", padx=18, pady=8)
        actions.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(actions, fg_color=COLOR_INPUT, progress_color=COLOR_PURPLE)
        self.progress.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(actions, text="Ready", text_color=COLOR_MUTED)
        self.status_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 14))

        self.download_button = ctk.CTkButton(actions, text="Download", height=38, command=self.start_download, fg_color=COLOR_PURPLE, hover_color=COLOR_PURPLE_HOVER, text_color=COLOR_TEXT)
        self.download_button.grid(row=0, column=1, rowspan=2, padx=(0, 14), pady=14)

        log_frame = ctk.CTkFrame(self, corner_radius=14, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_BORDER)
        log_frame.grid(row=6, column=0, sticky="nsew", padx=18, pady=(8, 18))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(log_frame, text="Activity", font=ctk.CTkFont(weight="bold"), text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.log_box = ctk.CTkTextbox(log_frame, height=150, fg_color=COLOR_INPUT, border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.log_box.configure(state="disabled")

    def choose_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(chosen)
            save_last_folder(chosen)


    def open_folder(self):
        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showerror("Missing folder", "Choose a download folder first.")
            return

        path = Path(folder)
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("Folder error", f"Could not open that folder:\n{e}")

    def log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def validate_inputs(self) -> tuple[str, str] | None:
        url = self.url_var.get().strip()
        folder = self.folder_var.get().strip()

        if not url:
            messagebox.showerror("Missing link", "Paste a video link first.")
            return None

        if not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showerror("Invalid link", "The link should start with http:// or https://")
            return None

        if not folder:
            messagebox.showerror("Missing folder", "Choose a download folder first.")
            return None

        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
            save_last_folder(folder)
        except Exception as e:
            messagebox.showerror("Folder error", f"Could not use that folder:\n{e}")
            return None

        return url, folder

    def start_download(self):
        if self.is_downloading:
            return

        validated = self.validate_inputs()
        if not validated:
            return

        url, folder = validated
        self.is_downloading = True
        self.download_button.configure(state="disabled", text="Downloading...")
        self.progress.set(0)
        self.status_label.configure(text="Starting...")
        self.log(f"Starting download: {url}")

        self.download_thread = threading.Thread(target=self.download_worker, args=(url, folder), daemon=True)
        self.download_thread.start()

    def build_format_selector(self) -> str:
        mode = self.mode_var.get()
        quality = self.quality_var.get()

        if mode == "Audio MP3":
            return "bestaudio/best"

        if quality == "Best":
            return "bestvideo+bestaudio/best"

        height = quality.replace("p", "")
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"

    def progress_hook(self, data):
        status = data.get("status")

        if status == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            speed = data.get("speed") or 0
            eta = data.get("eta")

            if total:
                percent = max(0, min(downloaded / total, 1))
                self.ui_queue.put(("progress", percent))
                pct_text = f"{percent * 100:.1f}%"
            else:
                pct_text = "Downloading..."

            speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "speed unknown"
            eta_text = f", ETA {eta}s" if eta is not None else ""
            self.ui_queue.put(("status", f"{pct_text} • {speed_text}{eta_text}"))

        elif status == "finished":
            filename = data.get("filename", "download")
            self.ui_queue.put(("progress", 1))
            self.ui_queue.put(("log", f"Finished downloading: {Path(filename).name}"))
            self.ui_queue.put(("status", "Processing file..."))

    def download_worker(self, url: str, folder: str):
        try:
            mode = self.mode_var.get()
            outtmpl = str(Path(folder) / "%(title).180B [%(id)s].%(ext)s")

            opts = {
                "outtmpl": outtmpl,
                "format": self.build_format_selector(),
                "noplaylist": not self.playlist_var.get(),
                "progress_hooks": [self.progress_hook],
                "logger": QueueLogger(self.ui_queue),
                "windowsfilenames": True,
                "restrictfilenames": False,
                "ignoreerrors": False,
                "overwrites": False,
            }

            ffmpeg_dir = bundled_ffmpeg_dir()
            if ffmpeg_dir:
                opts["ffmpeg_location"] = ffmpeg_dir

            if mode == "Video MP4":
                opts["merge_output_format"] = "mp4"
            else:
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            self.ui_queue.put(("done", "Download complete."))
        except Exception as e:
            self.ui_queue.put(("error", str(e)))

    def process_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "progress":
                    self.progress.set(float(payload))
                elif kind == "status":
                    self.status_label.configure(text=str(payload))
                elif kind == "log":
                    self.log(str(payload))
                elif kind == "error":
                    self.log(f"ERROR: {payload}")
                    self.status_label.configure(text="Error")
                    self.download_button.configure(state="normal", text="Download")
                    self.is_downloading = False
                    messagebox.showerror("Download failed", str(payload))
                elif kind == "done":
                    self.status_label.configure(text=str(payload))
                    self.log(str(payload))
                    self.download_button.configure(state="normal", text="Download")
                    self.is_downloading = False
        except queue.Empty:
            pass

        self.after(100, self.process_queue)


if __name__ == "__main__":
    app = DownloadApp()
    app.mainloop()
