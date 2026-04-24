import os
import shutil
import time
import zipfile
import subprocess
import urllib.request
import threading
import tkinter as tk
from tkinter import ttk, font


RYUJINX_URL = "https://git.ryujinx.app/Ryubing/Canary/releases/download/1.3.274/ryujinx-canary-1.3.274-win_x64.zip"
PRODKEYS_URL = "https://files.prodkeys.net/ProdKeys.NET-v22.1.0.zip"
FIRMWARE_URL = "https://github.com/THZoria/NX_Firmware/releases/download/22.1.0/Firmware.22.1.0.zip"

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
APPDATA = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
RYUJINX_CFG = os.path.join(APPDATA, "Ryujinx")
TEMP_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "_ryujinx_setup_tmp")

STEPS = [
    {
        "title": "Step 1   Ryujinx Emulator",
        "lines": [
            "Downloads the Ryujinx Canary build (v1.3.274)",
            "Extracts and renames the folder to  Ryujinx",
            "Moves it to your Desktop",
            "Creates a  games  subfolder inside it",
            "Launches Ryujinx.exe once so it generates its config folders",
            "Closes it automatically after 2 seconds",
        ],
    },
    {
        "title": "Step 2   Production Keys",
        "lines": [
            "Downloads the ProdKeys archive (v22.1.0)",
            "Extracts the two key files from the archive",
            "Copies them into  AppData/Roaming/Ryujinx/system",
            "Deletes the ZIP and temporary folder afterwards",
        ],
    },
    {
        "title": "Step 3   Nintendo Firmware",
        "lines": [
            "Downloads the Switch Firmware archive (v22.1.0)",
            "Moves the ZIP into  AppData/Roaming/Ryujinx/bis/system/Contents/registered",
            "Extracts it directly into that folder",
            "Deletes the ZIP file once extraction is complete",
        ],
    },
]


class SetupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ryujinx Setup")
        self.geometry("700x820")
        self.resizable(False, False)
        self.configure(bg="#0a0a0a")
        self._build_ui()

    def _build_ui(self):
        fnt_title  = font.Font(family="Consolas", size=18, weight="bold")
        fnt_sub    = font.Font(family="Consolas", size=9)
        fnt_step   = font.Font(family="Consolas", size=10, weight="bold")
        fnt_line   = font.Font(family="Consolas", size=9)
        fnt_btn    = font.Font(family="Consolas", size=13, weight="bold")
        fnt_log    = font.Font(family="Consolas", size=9)
        fnt_status = font.Font(family="Consolas", size=9)
        fnt_credit = font.Font(family="Consolas", size=8)

        tk.Label(self, text="RYUJINX SETUP", font=fnt_title,
                 bg="#0a0a0a", fg="#e8ff00").pack(pady=(26, 2))
        tk.Label(self, text="Automated installer for Ryujinx   ProdKeys   Firmware",
                 font=fnt_sub, bg="#0a0a0a", fg="#aaaaaa").pack()

        tk.Frame(self, height=1, bg="#2a2a2a").pack(fill="x", padx=28, pady=14)

        self.step_status_labels = []
        self.step_frames = []
        self.step_line_labels = []

        for i, step in enumerate(STEPS):
            card = tk.Frame(self, bg="#161616", bd=0, highlightthickness=1,
                            highlightbackground="#2a2a2a")
            card.pack(fill="x", padx=28, pady=5)
            self.step_frames.append(card)

            header = tk.Frame(card, bg="#161616")
            header.pack(fill="x", padx=14, pady=(10, 4))

            tk.Label(header, text=step["title"], font=fnt_step,
                     bg="#161616", fg="#cccccc", anchor="w").pack(side="left")

            status_lbl = tk.Label(header, text="waiting", font=fnt_sub,
                                  bg="#161616", fg="#555555", anchor="e")
            status_lbl.pack(side="right")
            self.step_status_labels.append(status_lbl)

            line_labels = []
            for line in step["lines"]:
                row = tk.Frame(card, bg="#161616")
                row.pack(fill="x", padx=18, pady=1)
                tk.Label(row, text="  ", font=fnt_line,
                         bg="#161616", fg="#555555").pack(side="left")
                lbl = tk.Label(row, text=line, font=fnt_line,
                               bg="#161616", fg="#888888", anchor="w")
                lbl.pack(side="left")
                line_labels.append(lbl)

            self.step_line_labels.append(line_labels)
            tk.Frame(card, height=8, bg="#161616").pack()

        tk.Frame(self, height=1, bg="#2a2a2a").pack(fill="x", padx=28, pady=12)

        self.progress_var = tk.DoubleVar()
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Y.Horizontal.TProgressbar",
                        troughcolor="#1a1a1a", background="#e8ff00",
                        bordercolor="#0a0a0a", lightcolor="#e8ff00", darkcolor="#e8ff00")
        self.bar = ttk.Progressbar(self, variable=self.progress_var,
                                   maximum=100, style="Y.Horizontal.TProgressbar")
        self.bar.pack(fill="x", padx=28)

        self.status_var = tk.StringVar(value="Ready to install.")
        tk.Label(self, textvariable=self.status_var, font=fnt_status,
                 bg="#0a0a0a", fg="#aaaaaa", anchor="w").pack(fill="x", padx=30, pady=(6, 2))

        log_frame = tk.Frame(self, bg="#0a0a0a")
        log_frame.pack(padx=28, pady=(4, 6), fill="both", expand=True)
        self.log_box = tk.Text(log_frame, height=5, bg="#0d0d0d", fg="#888888",
                               font=fnt_log, bd=0, relief="flat",
                               state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True)

        self.start_btn = tk.Button(self, text="START INSTALL",
                                   font=fnt_btn,
                                   bg="#e8ff00", fg="#0a0a0a",
                                   activebackground="#c8df00",
                                   activeforeground="#0a0a0a",
                                   bd=0, cursor="hand2",
                                   command=self._start, pady=16)
        self.start_btn.pack(padx=28, fill="x", pady=(4, 6))

        tk.Label(self, text="made by L61r", font=fnt_credit,
                 bg="#0a0a0a", fg="#333333").pack(pady=(0, 10))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.status_var.set(msg)

    def _set_step_active(self, index):
        card = self.step_frames[index]
        card.configure(highlightbackground="#e8ff00")
        self.step_status_labels[index].configure(text="running", fg="#e8ff00")
        for widget in card.winfo_children():
            self._recolor_bg(widget, "#161616")
        for lbl in self.step_line_labels[index]:
            lbl.configure(fg="#dddddd")
        title_widget = card.winfo_children()[0].winfo_children()[0]
        title_widget.configure(fg="#e8ff00")

    def _set_step_done(self, index):
        card = self.step_frames[index]
        card.configure(highlightbackground="#39ff14")
        self.step_status_labels[index].configure(text="done", fg="#39ff14")
        for lbl in self.step_line_labels[index]:
            lbl.configure(fg="#aaaaaa")
        title_widget = card.winfo_children()[0].winfo_children()[0]
        title_widget.configure(fg="#39ff14")

    def _recolor_bg(self, widget, bg):
        try:
            widget.configure(bg=bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recolor_bg(child, bg)

    def _start(self):
        self.start_btn.configure(state="disabled", text="INSTALLING ...")
        threading.Thread(target=self._run, daemon=True).start()

    def _download(self, url, dest, label):
        self._log(f"Downloading  {label} ...")
        def hook(count, block, total):
            if total > 0:
                mb_done  = count * block / 1_048_576
                mb_total = total / 1_048_576
                pct = min(count * block / total * 100, 100)
                self.progress_var.set(pct)
                self.status_var.set(f"Downloading {label}   {mb_done:.1f} MB / {mb_total:.1f} MB   ({pct:.0f}%)")
        urllib.request.urlretrieve(url, dest, reporthook=hook)
        self.progress_var.set(100)

    def _extract(self, zip_path, extract_to):
        self._log(f"Extracting  {os.path.basename(zip_path)} ...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_to)
        self._log("Extraction complete.")

    def _run(self):
        try:
            os.makedirs(TEMP_DIR, exist_ok=True)

            self._set_step_active(0)
            self.progress_var.set(0)
            ryu_zip     = os.path.join(TEMP_DIR, "ryujinx.zip")
            ryu_extract = os.path.join(TEMP_DIR, "ryujinx_extracted")
            ryu_dest    = os.path.join(DESKTOP, "Ryujinx")

            self._download(RYUJINX_URL, ryu_zip, "Ryujinx")
            os.makedirs(ryu_extract, exist_ok=True)
            self._extract(ryu_zip, ryu_extract)
            os.remove(ryu_zip)
            self._log("Deleted ryujinx.zip")

            entries = os.listdir(ryu_extract)
            src = (os.path.join(ryu_extract, entries[0])
                   if len(entries) == 1 and os.path.isdir(os.path.join(ryu_extract, entries[0]))
                   else ryu_extract)

            if os.path.exists(ryu_dest):
                shutil.rmtree(ryu_dest)
            shutil.move(src, ryu_dest)
            self._log(f"Moved to Desktop  {ryu_dest}")

            os.makedirs(os.path.join(ryu_dest, "games"), exist_ok=True)
            self._log("Created games folder inside Ryujinx")

            ryu_exe = os.path.join(ryu_dest, "Ryujinx.exe")
            if os.path.exists(ryu_exe):
                self._log("Launching Ryujinx.exe to generate config folders ...")
                proc = subprocess.Popen([ryu_exe])
                time.sleep(2)
                proc.terminate()
                time.sleep(1)
                self._log("Ryujinx closed after 2 seconds")
            self._set_step_done(0)

            self._set_step_active(1)
            self.progress_var.set(0)
            keys_zip     = os.path.join(TEMP_DIR, "prodkeys.zip")
            keys_extract = os.path.join(TEMP_DIR, "prodkeys_extracted")
            keys_dest    = os.path.join(RYUJINX_CFG, "system")

            self._download(PRODKEYS_URL, keys_zip, "ProdKeys")
            os.makedirs(keys_extract, exist_ok=True)
            self._extract(keys_zip, keys_extract)

            keys_inner = os.path.join(keys_extract, "Keys-22.1.0")
            if not os.path.exists(keys_inner):
                sub = [e for e in os.listdir(keys_extract) if os.path.isdir(os.path.join(keys_extract, e))]
                keys_inner = os.path.join(keys_extract, sub[0]) if sub else keys_extract

            os.makedirs(keys_dest, exist_ok=True)
            for f in os.listdir(keys_inner):
                shutil.move(os.path.join(keys_inner, f), os.path.join(keys_dest, f))
                self._log(f"Installed key file  {f}")

            os.remove(keys_zip)
            shutil.rmtree(keys_extract)
            self._log("Deleted prodkeys.zip and temp folder")
            self._set_step_done(1)

            self._set_step_active(2)
            self.progress_var.set(0)
            fw_zip  = os.path.join(TEMP_DIR, "firmware.zip")
            fw_dest = os.path.join(RYUJINX_CFG, "bis", "system", "Contents", "registered")

            self._download(FIRMWARE_URL, fw_zip, "Firmware")
            os.makedirs(fw_dest, exist_ok=True)
            fw_moved = os.path.join(fw_dest, "Firmware.22.1.0.zip")
            shutil.move(fw_zip, fw_moved)
            self._log(f"Moved firmware ZIP to  {fw_dest}")
            self._extract(fw_moved, fw_dest)
            os.remove(fw_moved)
            self._log("Deleted Firmware.22.1.0.zip")
            self._set_step_done(2)

            shutil.rmtree(TEMP_DIR, ignore_errors=True)

            self.status_var.set("All done! Ryujinx is ready to use.")
            self.start_btn.configure(state="normal", text="INSTALLATION COMPLETE",
                                     bg="#39ff14", fg="#0a0a0a")

        except Exception as e:
            self._log(f"ERROR  {e}")
            self.start_btn.configure(state="normal", text="RETRY",
                                     bg="#ff4444", fg="#ffffff")


if __name__ == "__main__":
    app = SetupApp()
    app.mainloop()

