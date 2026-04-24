import os
import shutil
import time
import zipfile
import subprocess
import urllib.request
import urllib.error
import ssl
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, font

# SSL-Fix für PyInstaller .exe (kein CA-Bundle eingebaut)
ssl._create_default_https_context = ssl._create_unverified_context


RYUJINX_URL  = "https://file.garden/aerQEN7dt0EuhaYR/ryujinx-canary-1.3.274-win_x64.zip"
PRODKEYS_URL = "https://files.prodkeys.net/ProdKeys.NET-v22.1.0.zip"
FIRMWARE_URL = "https://github.com/THZoria/NX_Firmware/releases/download/22.1.0/Firmware.22.1.0.zip"
VCREDIST_URL = "https://aka.ms/vc14/vc_redist.x64.exe"

DESKTOP     = os.path.join(os.path.expanduser("~"), "Desktop")
APPDATA     = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
RYUJINX_CFG = os.path.join(APPDATA, "Ryujinx")
TEMP_DIR    = os.path.join(os.path.expanduser("~"), "Downloads", "_ryujinx_setup_tmp")

# Sekunden die Ryujinx offen bleibt damit AppData Ordner entstehen
RYUJINX_WAIT = 10

STEPS = [
    {
        "title": "Step 1   Ryujinx Emulator",
        "lines": [
            "Downloads the Ryujinx Canary build (v1.3.274)",
            "Extracts and renames the folder to  Ryujinx",
            "Moves it to your Desktop",
            "Creates a  games  subfolder inside it",
            f"Launches Ryujinx.exe for {RYUJINX_WAIT}s to generate config folders",
            f"Closes it automatically after {RYUJINX_WAIT} seconds",
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
            "Extracts directly into  AppData/Roaming/Ryujinx/bis/system/Contents/registered",
            "Deletes the ZIP file once extraction is complete",
        ],
    },
]


class SetupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ryujinx Setup")
        self.resizable(True, True)
        self.minsize(600, 480)
        self.configure(bg="#0a0a0a")

        # Fenster zentriert, passt sich kleinen Bildschirmen an
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(700, sw - 40)
        h  = min(860, sh - 60)
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._vcredist_shown = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        fnt_title   = font.Font(family="Consolas", size=16, weight="bold")
        fnt_sub     = font.Font(family="Consolas", size=9)
        fnt_step    = font.Font(family="Consolas", size=10, weight="bold")
        fnt_line    = font.Font(family="Consolas", size=9)
        fnt_btn     = font.Font(family="Consolas", size=11, weight="bold")
        fnt_log     = font.Font(family="Consolas", size=9)
        fnt_status  = font.Font(family="Consolas", size=9)
        fnt_vcredit = font.Font(family="Consolas", size=9, weight="bold")

        # ── Canvas + scrollbar (scrollable content) ───────────────────────────
        wrap = tk.Frame(self, bg="#0a0a0a")
        wrap.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(wrap, bg="#0a0a0a", highlightthickness=0, bd=0)
        scrollbar    = ttk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg="#0a0a0a")
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win_id, width=e.width))
        self.bind_all("<MouseWheel>",
                      lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── Content ───────────────────────────────────────────────────────────
        inner = self._inner   # shorthand

        tk.Label(inner, text="RYUJINX SETUP", font=fnt_title,
                 bg="#0a0a0a", fg="#e8ff00").pack(pady=(22, 2))
        tk.Label(inner, text="Automated installer for Ryujinx   ProdKeys   Firmware",
                 font=fnt_sub, bg="#0a0a0a", fg="#555555").pack()

        tk.Frame(inner, height=1, bg="#222222").pack(fill="x", padx=28, pady=14)

        self.step_status_labels = []
        self.step_frames = []

        for step in STEPS:
            card = tk.Frame(inner, bg="#111111", bd=0,
                            highlightthickness=1, highlightbackground="#222222")
            card.pack(fill="x", padx=28, pady=5)
            self.step_frames.append(card)

            header = tk.Frame(card, bg="#111111")
            header.pack(fill="x", padx=14, pady=(10, 4))
            tk.Label(header, text=step["title"], font=fnt_step,
                     bg="#111111", fg="#444444", anchor="w").pack(side="left")
            sl = tk.Label(header, text="waiting", font=fnt_sub,
                          bg="#111111", fg="#333333", anchor="e")
            sl.pack(side="right")
            self.step_status_labels.append(sl)

            for line in step["lines"]:
                row = tk.Frame(card, bg="#111111")
                row.pack(fill="x", padx=18, pady=1)
                tk.Label(row, text="  ", font=fnt_line,
                         bg="#111111", fg="#333333").pack(side="left")
                tk.Label(row, text=line, font=fnt_line, bg="#111111",
                         fg="#333333", anchor="w", justify="left",
                         wraplength=500).pack(side="left", fill="x", expand=True)

            tk.Frame(card, height=8, bg="#111111").pack()

        tk.Frame(inner, height=1, bg="#222222").pack(fill="x", padx=28, pady=14)

        # Progress bar
        pf = tk.Frame(inner, bg="#0a0a0a")
        pf.pack(fill="x", padx=28)
        self.progress_var = tk.DoubleVar()
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Y.Horizontal.TProgressbar",
                        troughcolor="#1a1a1a", background="#e8ff00",
                        bordercolor="#0a0a0a", lightcolor="#e8ff00", darkcolor="#e8ff00")
        self.bar = ttk.Progressbar(pf, variable=self.progress_var,
                                   maximum=100, style="Y.Horizontal.TProgressbar")
        self.bar.pack(fill="x")

        # Status text
        self.status_var = tk.StringVar(value="Ready to install.")
        tk.Label(inner, textvariable=self.status_var, font=fnt_status,
                 bg="#0a0a0a", fg="#666666", anchor="w",
                 wraplength=640, justify="left").pack(fill="x", padx=30, pady=(6, 2))

        # Log box
        lf = tk.Frame(inner, bg="#0a0a0a")
        lf.pack(padx=28, pady=(4, 6), fill="x")
        self.log_box = tk.Text(lf, height=7, bg="#0d0d0d", fg="#444444",
                               font=fnt_log, bd=0, relief="flat",
                               state="disabled", wrap="word",
                               insertbackground="#e8ff00")
        self.log_box.pack(fill="x")

        # vcredist button — hidden until a launch error occurs
        self.vcredist_btn = tk.Button(
            inner,
            text="⚠   Download Visual C++ Redistributable   (fix if Ryujinx won't start)",
            font=fnt_vcredit,
            bg="#2a1500", fg="#ff9900",
            activebackground="#3d2000", activeforeground="#ffbb44",
            bd=0, cursor="hand2", pady=9,
            command=lambda: webbrowser.open(VCREDIST_URL)
        )
        # not packed yet — appears only when needed

        # Start button
        self.start_btn = tk.Button(inner, text="START INSTALL",
                                   font=fnt_btn,
                                   bg="#e8ff00", fg="#0a0a0a",
                                   activebackground="#c8df00",
                                   activeforeground="#0a0a0a",
                                   bd=0, cursor="hand2",
                                   command=self._start, pady=13)
        self.start_btn.pack(padx=28, fill="x", pady=(6, 26))

    # ── Helpers ───────────────────────────────────────────────────────────────
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
        self._recolor(card, "#e8ff00")

    def _set_step_done(self, index):
        card = self.step_frames[index]
        card.configure(highlightbackground="#39ff14")
        self.step_status_labels[index].configure(text="done", fg="#39ff14")
        self._recolor(card, "#39ff14")

    def _recolor(self, widget, fg):
        try:
            widget.configure(bg="#111111")
        except Exception:
            pass
        try:
            widget.configure(fg=fg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recolor(child, fg)

    def _show_vcredist(self):
        if not self._vcredist_shown:
            self._vcredist_shown = True
            self.vcredist_btn.pack(in_=self._inner, padx=28, fill="x",
                                   pady=(0, 6), before=self.start_btn)
            # Scroll down so button is visible
            self._canvas.after(100, lambda: self._canvas.yview_moveto(1.0))

    def _show_firmware_guide(self, fw_path):
        """Popup that guides the user through the manual firmware install in Ryujinx."""
        popup = tk.Toplevel(self)
        popup.title("Install Firmware in Ryujinx")
        popup.configure(bg="#0a0a0a")
        popup.resizable(False, False)
        popup.grab_set()   # modal — stays on top
        popup.lift()

        # Center on screen
        popup.update_idletasks()
        pw, ph = 540, 460
        sx = self.winfo_screenwidth()
        sy = self.winfo_screenheight()
        popup.geometry(f"{pw}x{ph}+{(sx-pw)//2}+{(sy-ph)//2}")

        fnt_h  = font.Font(family="Consolas", size=12, weight="bold")
        fnt_b  = font.Font(family="Consolas", size=9,  weight="bold")
        fnt_s  = font.Font(family="Consolas", size=9)
        fnt_c  = font.Font(family="Consolas", size=9)
        fnt_btn= font.Font(family="Consolas", size=11, weight="bold")

        tk.Label(popup, text="🎮  Install Firmware in Ryujinx",
                 font=fnt_h, bg="#0a0a0a", fg="#e8ff00").pack(pady=(22, 4))
        tk.Label(popup,
                 text="Ryujinx is now open. Follow these steps:",
                 font=fnt_s, bg="#0a0a0a", fg="#666666").pack(pady=(0, 14))

        steps = [
            ("1", "In Ryujinx click  Actions  in the top menu bar"),
            ("2", "Click  Install Firmware"),
            ("3", "Click  Install Firmware (XCI or ZIP)"),
            ("4", f"Select the file on your Desktop:\nFirmware.22.1.0.zip"),
            ("5", "Wait for the install to finish, then come back here"),
        ]

        for num, text in steps:
            row = tk.Frame(popup, bg="#111111", highlightthickness=1,
                           highlightbackground="#2a2a2a")
            row.pack(fill="x", padx=24, pady=3)

            tk.Label(row, text=num, font=fnt_b, bg="#e8ff00", fg="#0a0a0a",
                     width=3, anchor="center").pack(side="left", ipady=10)

            tk.Label(row, text="  " + text, font=fnt_b, bg="#111111",
                     fg="#cccccc", anchor="w", justify="left",
                     wraplength=420).pack(side="left", fill="x",
                                          expand=True, padx=6, pady=8)

        # Show firmware path as copyable text
        tk.Label(popup, text="Firmware ZIP is on your Desktop:",
                 font=fnt_s, bg="#0a0a0a", fg="#555555").pack(pady=(16, 2))
        path_var = tk.StringVar(value=fw_path)
        path_entry = tk.Entry(popup, textvariable=path_var, font=fnt_c,
                              bg="#1a1a1a", fg="#e8ff00", bd=0,
                              readonlybackground="#1a1a1a",
                              justify="center", state="readonly")
        path_entry.pack(fill="x", padx=24, ipady=5)

        def on_done():
            popup.destroy()
            self._fw_done_event.set()

        tk.Button(popup, text="✅   I installed the firmware — continue",
                  font=fnt_btn, bg="#39ff14", fg="#0a0a0a",
                  activebackground="#22cc00", bd=0, cursor="hand2",
                  pady=12, command=on_done).pack(
                      fill="x", padx=24, pady=(18, 24))

        popup.protocol("WM_DELETE_WINDOW", on_done)  # closing = done

    def _start(self):
        self.start_btn.configure(state="disabled", text="INSTALLING  ...")
        threading.Thread(target=self._run, daemon=True).start()

    # ── Download ──────────────────────────────────────────────────────────────
    def _download(self, url, dest, label):
        self._log(f"Downloading  {label} ...")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req) as resp:
            total      = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk      = 1024 * 64
            with open(dest, "wb") as f:
                while True:
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)
                    if total > 0:
                        pct = min(downloaded / total * 100, 100)
                        self.progress_var.set(pct)
                        self.status_var.set(
                            f"Downloading {label}   "
                            f"{downloaded/1_048_576:.1f} / {total/1_048_576:.1f} MB"
                            f"   ({pct:.0f}%)"
                        )
        self.progress_var.set(100)

    # ── Extract ───────────────────────────────────────────────────────────────
    def _extract(self, zip_path, extract_to):
        if not zipfile.is_zipfile(zip_path):
            with open(zip_path, "rb") as f:
                preview = f.read(120)
            raise ValueError(
                f"Downloaded file is not a ZIP (bot-protection or wrong link).\n"
                f"First bytes: {preview}"
            )
        self._log(f"Extracting  {os.path.basename(zip_path)} ...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_to)
        self._log("Extraction complete.")

    def _find_ryujinx_exe(self, base_dir):
        for root, dirs, files in os.walk(base_dir):
            if "Ryujinx.exe" in files:
                return root
        return None

    def _find_key_files(self, base_dir):
        found = {}
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f in ("prod.keys", "title.keys"):
                    found[f] = os.path.join(root, f)
        return found

    # ── Main install ──────────────────────────────────────────────────────────
    def _run(self):
        try:
            os.makedirs(TEMP_DIR, exist_ok=True)

            # ── Step 1: Ryujinx ───────────────────────────────────────────────
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

            exe_folder = self._find_ryujinx_exe(ryu_extract)
            if exe_folder is None:
                raise FileNotFoundError(
                    f"Ryujinx.exe not found after extraction. "
                    f"Contents: {os.listdir(ryu_extract)}"
                )
            self._log(f"Found Ryujinx.exe in: {exe_folder}")

            if os.path.exists(ryu_dest):
                shutil.rmtree(ryu_dest)
            shutil.move(exe_folder, ryu_dest)
            shutil.rmtree(ryu_extract, ignore_errors=True)
            self._log(f"Moved to Desktop: {ryu_dest}")

            os.makedirs(os.path.join(ryu_dest, "games"), exist_ok=True)
            self._log("Created  games  folder inside Ryujinx")

            # Launch Ryujinx so it creates AppData config folders
            ryu_exe        = os.path.join(ryu_dest, "Ryujinx.exe")
            ryu_launch_ok  = False
            if os.path.exists(ryu_exe):
                self._log(f"Launching Ryujinx.exe for {RYUJINX_WAIT}s ...")
                try:
                    proc = subprocess.Popen(
                        [ryu_exe],
                        cwd=ryu_dest,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    )
                    for i in range(RYUJINX_WAIT, 0, -1):
                        time.sleep(1)
                        self.status_var.set(
                            f"Installing...  Ryujinx running, closing in {i}s"
                        )
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    self._log("Ryujinx closed.")
                    ryu_launch_ok = True
                except Exception as launch_err:
                    self._log(f"WARNING: Could not launch Ryujinx: {launch_err}")
                    self._log("Tip: Missing Visual C++ Redistributable can cause this.")
                    self.after(0, self._show_vcredist)
            else:
                self._log("WARNING: Ryujinx.exe not found, skipping launch.")

            # If launch failed, create AppData folders manually so keys/firmware install works
            if not ryu_launch_ok:
                manual_dir = os.path.join(RYUJINX_CFG, "system")
                os.makedirs(manual_dir, exist_ok=True)
                self._log(f"Manually created: {manual_dir}")

            self._set_step_done(0)

            # ── Step 2: ProdKeys ──────────────────────────────────────────────
            self._set_step_active(1)
            self.progress_var.set(0)
            keys_zip     = os.path.join(TEMP_DIR, "prodkeys.zip")
            keys_extract = os.path.join(TEMP_DIR, "prodkeys_extracted")
            keys_dest    = os.path.join(RYUJINX_CFG, "system")

            self._download(PRODKEYS_URL, keys_zip, "ProdKeys")
            os.makedirs(keys_extract, exist_ok=True)
            self._extract(keys_zip, keys_extract)

            key_files = self._find_key_files(keys_extract)
            if not key_files:
                raise FileNotFoundError(
                    f"prod.keys / title.keys not found. "
                    f"Contents: {os.listdir(keys_extract)}"
                )

            os.makedirs(keys_dest, exist_ok=True)
            for fname, fpath in key_files.items():
                shutil.copy2(fpath, os.path.join(keys_dest, fname))
                self._log(f"Installed: {fname}")

            os.remove(keys_zip)
            shutil.rmtree(keys_extract, ignore_errors=True)
            self._log("Deleted prodkeys.zip and temp folder")
            self._set_step_done(1)

            # ── Step 3: Firmware ──────────────────────────────────────────────
            self._set_step_active(2)
            self.progress_var.set(0)
            fw_zip  = os.path.join(TEMP_DIR, "firmware.zip")

            self._download(FIRMWARE_URL, fw_zip, "Firmware")
            self._log("Firmware downloaded — do NOT extract, Ryujinx will handle it.")

            # Copy firmware zip to Desktop so user can find it easily
            fw_desktop = os.path.join(DESKTOP, "Firmware.22.1.0.zip")
            shutil.copy2(fw_zip, fw_desktop)
            os.remove(fw_zip)
            self._log(f"Copied firmware ZIP to Desktop: {fw_desktop}")

            # Open Ryujinx so the user can install firmware manually
            ryu_exe = os.path.join(ryu_dest, "Ryujinx.exe")
            if os.path.exists(ryu_exe):
                self._log("Opening Ryujinx for firmware install step ...")
                subprocess.Popen([ryu_exe], cwd=ryu_dest)
                time.sleep(2)  # short pause so window is visible before popup

            # Show guided popup — blocks until user clicks "Done"
            self.after(0, lambda: self._show_firmware_guide(fw_desktop))
            self._fw_done_event = threading.Event()
            self._fw_done_event.wait()  # wait here until user confirms

            # Cleanup firmware zip from Desktop
            if os.path.exists(fw_desktop):
                os.remove(fw_desktop)
                self._log("Deleted Firmware.22.1.0.zip from Desktop")

            self._set_step_done(2)

            # ── Done ──────────────────────────────────────────────────────────
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            self.status_var.set("All done!  Ryujinx is ready on your Desktop.")
            self.start_btn.configure(
                state="normal", text="INSTALLATION COMPLETE",
                bg="#39ff14", fg="#0a0a0a"
            )

        except Exception as e:
            self._log(f"ERROR:  {e}")
            self.status_var.set("Error — see log above.")
            self.start_btn.configure(
                state="normal", text="RETRY",
                bg="#ff4444", fg="#ffffff"
            )


if __name__ == "__main__":
    app = SetupApp()
    app.mainloop()
