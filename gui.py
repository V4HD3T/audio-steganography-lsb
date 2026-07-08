"""
gui.py — Tkinter Desktop GUI
=============================
A drag-and-drop-friendly desktop application covering:

  Tab 1 — Embed    : Select audio + image, configure options, embed.
  Tab 2 — Extract  : Select stego audio, recover image.
  Tab 3 — Analyse  : Run RS + SPA steganalysis on any WAV file.
  Tab 4 — Capacity : Pre-flight capacity check.

All long-running operations execute in a background thread so the
UI stays responsive.  Results are streamed back to a scrolled log widget.

Dependencies:
    pip install Pillow    (tkinter is part of Python's stdlib)
"""

import io
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox


# ---------------------------------------------------------------------------
# Output redirect: capture print() output into the GUI log
# ---------------------------------------------------------------------------

class _StreamToLog:
    """File-like object that writes to a tkinter ScrolledText widget."""

    def __init__(self, log_widget: scrolledtext.ScrolledText) -> None:
        self._log = log_widget

    def write(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert(tk.END, text)
        self._log.see(tk.END)
        self._log.configure(state="disabled")

    def flush(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

def _file_row(parent, label: str, filetypes: list, row: int) -> tk.StringVar:
    """Create a label + entry + Browse button row and return the StringVar."""
    var = tk.StringVar()
    tk.Label(parent, text=label, anchor="w", width=16).grid(row=row, column=0, sticky="w", pady=3)
    tk.Entry(parent, textvariable=var, width=42).grid(row=row, column=1, pady=3, padx=(4, 4))
    tk.Button(
        parent, text="Browse…",
        command=lambda: var.set(filedialog.askopenfilename(filetypes=filetypes))
    ).grid(row=row, column=2, pady=3)
    return var


def _save_row(parent, label: str, filetypes: list, row: int) -> tk.StringVar:
    """Create a label + entry + Save-As button row."""
    var = tk.StringVar()
    tk.Label(parent, text=label, anchor="w", width=16).grid(row=row, column=0, sticky="w", pady=3)
    tk.Entry(parent, textvariable=var, width=42).grid(row=row, column=1, pady=3, padx=(4, 4))
    tk.Button(
        parent, text="Save As…",
        command=lambda: var.set(filedialog.asksaveasfilename(filetypes=filetypes))
    ).grid(row=row, column=2, pady=3)
    return var


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class StegoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio Steganography")
        self.resizable(False, False)
        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._tab_embed    = ttk.Frame(notebook)
        self._tab_extract  = ttk.Frame(notebook)
        self._tab_analyse  = ttk.Frame(notebook)
        self._tab_capacity = ttk.Frame(notebook)

        notebook.add(self._tab_embed,    text="  Embed  ")
        notebook.add(self._tab_extract,  text="  Extract  ")
        notebook.add(self._tab_analyse,  text="  Analyse  ")
        notebook.add(self._tab_capacity, text="  Capacity  ")

        self._build_embed_tab()
        self._build_extract_tab()
        self._build_analyse_tab()
        self._build_capacity_tab()
        self._build_log()

    def _build_embed_tab(self) -> None:
        f = self._tab_embed
        AUDIO = [("Audio files", "*.wav *.mp3 *.flac"), ("All files", "*.*")]
        IMAGE = [("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        WAV   = [("WAV files", "*.wav")]

        self._embed_audio  = _file_row(f, "Carrier audio:", AUDIO, 0)
        self._embed_image  = _file_row(f, "Image to hide:", IMAGE, 1)
        self._embed_output = _save_row(f, "Stego output:",  WAV,   2)

        # Options row
        opts = tk.Frame(f)
        opts.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)

        tk.Label(opts, text="LSB depth:").pack(side="left")
        self._embed_lsb = ttk.Combobox(opts, values=["1", "2", "3"], width=4, state="readonly")
        self._embed_lsb.set("1")
        self._embed_lsb.pack(side="left", padx=(4, 16))

        tk.Label(opts, text="Password:").pack(side="left")
        self._embed_pw = tk.Entry(opts, show="*", width=14)
        self._embed_pw.pack(side="left", padx=(4, 16))

        tk.Label(opts, text="PRNG seed:").pack(side="left")
        self._embed_seed = tk.Entry(opts, width=8)
        self._embed_seed.pack(side="left", padx=(4, 16))

        self._embed_ecc = tk.BooleanVar()
        tk.Checkbutton(opts, text="Reed-Solomon ECC", variable=self._embed_ecc).pack(side="left")

        tk.Button(f, text="  Embed Image  ", command=self._run_embed,
                  bg="#1976D2", fg="white", padx=8).grid(row=4, column=0, columnspan=3, pady=8)

    def _build_extract_tab(self) -> None:
        f = self._tab_extract
        AUDIO = [("WAV files", "*.wav")]
        IMAGE = [("PNG image", "*.png")]

        self._extr_audio  = _file_row(f, "Stego audio:",   AUDIO, 0)
        self._extr_output = _save_row(f, "Output image:",  IMAGE, 1)

        opts = tk.Frame(f)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)

        tk.Label(opts, text="LSB depth:").pack(side="left")
        self._extr_lsb = ttk.Combobox(opts, values=["1", "2", "3"], width=4, state="readonly")
        self._extr_lsb.set("1")
        self._extr_lsb.pack(side="left", padx=(4, 16))

        tk.Label(opts, text="Password:").pack(side="left")
        self._extr_pw = tk.Entry(opts, show="*", width=14)
        self._extr_pw.pack(side="left", padx=(4, 16))

        tk.Label(opts, text="PRNG seed:").pack(side="left")
        self._extr_seed = tk.Entry(opts, width=8)
        self._extr_seed.pack(side="left", padx=(4, 16))

        tk.Button(f, text="  Extract Image  ", command=self._run_extract,
                  bg="#388E3C", fg="white", padx=8).grid(row=3, column=0, columnspan=3, pady=8)

    def _build_analyse_tab(self) -> None:
        f = self._tab_analyse
        AUDIO = [("WAV files", "*.wav"), ("All files", "*.*")]
        self._anal_audio = _file_row(f, "Audio file:", AUDIO, 0)
        tk.Button(f, text="  Run Steganalysis  ", command=self._run_analyse,
                  bg="#7B1FA2", fg="white", padx=8).grid(row=1, column=0, columnspan=3, pady=12)

    def _build_capacity_tab(self) -> None:
        f = self._tab_capacity
        AUDIO = [("WAV files", "*.wav")]
        IMAGE = [("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]

        self._cap_audio = _file_row(f, "Carrier audio:", AUDIO, 0)
        self._cap_image = _file_row(f, "Image to check:", IMAGE, 1)

        opts = tk.Frame(f)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)

        self._cap_ecc = tk.BooleanVar()
        self._cap_enc = tk.BooleanVar()
        tk.Checkbutton(opts, text="Include ECC overhead",     variable=self._cap_ecc).pack(side="left", padx=8)
        tk.Checkbutton(opts, text="Include AES-GCM overhead", variable=self._cap_enc).pack(side="left", padx=8)

        tk.Button(f, text="  Check Capacity  ", command=self._run_capacity,
                  bg="#F57C00", fg="white", padx=8).grid(row=3, column=0, columnspan=3, pady=8)

    def _build_log(self) -> None:
        """Build the shared scrolled log at the bottom."""
        frame = tk.LabelFrame(self, text="Log", padx=4, pady=4)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log = scrolledtext.ScrolledText(frame, height=10, state="disabled",
                                               font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4")
        self._log.pack(fill="both", expand=True)
        sys.stdout = _StreamToLog(self._log)

    # -----------------------------------------------------------------------
    # Background runners
    # -----------------------------------------------------------------------

    def _run_in_thread(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def _run_embed(self) -> None:
        audio  = self._embed_audio.get()
        image  = self._embed_image.get()
        output = self._embed_output.get()
        depth  = int(self._embed_lsb.get())
        pw     = self._embed_pw.get() or None
        ecc    = self._embed_ecc.get()
        seed_s = self._embed_seed.get().strip()
        seed   = int(seed_s) if seed_s else None

        if not audio or not image or not output:
            messagebox.showerror("Missing input", "Please fill in all file paths.")
            return

        def task():
            try:
                from embedder import embed
                from formats  import load_as_wav, cleanup_temp
                tmp = None
                if not audio.lower().endswith(".wav"):
                    tmp = load_as_wav(audio)
                    src = tmp
                else:
                    src = audio
                embed(src, output, image, lsb_depth=depth,
                      password=pw, use_ecc=ecc, prng_seed=seed)
                if tmp:
                    cleanup_temp(tmp)
            except Exception as ex:
                print(f"[ERROR] {ex}")

        self._run_in_thread(task)

    def _run_extract(self) -> None:
        audio  = self._extr_audio.get()
        output = self._extr_output.get()
        depth  = int(self._extr_lsb.get())
        pw     = self._extr_pw.get() or None
        seed_s = self._extr_seed.get().strip()
        seed   = int(seed_s) if seed_s else None

        if not audio or not output:
            messagebox.showerror("Missing input", "Please fill in all file paths.")
            return

        def task():
            try:
                from embedder import extract
                extract(audio, output, lsb_depth=depth, password=pw, prng_seed=seed)
            except Exception as ex:
                print(f"[ERROR] {ex}")

        self._run_in_thread(task)

    def _run_analyse(self) -> None:
        audio = self._anal_audio.get()
        if not audio:
            messagebox.showerror("Missing input", "Please select an audio file.")
            return

        def task():
            try:
                from steganalysis import analyse
                analyse(audio)
            except Exception as ex:
                print(f"[ERROR] {ex}")

        self._run_in_thread(task)

    def _run_capacity(self) -> None:
        audio = self._cap_audio.get()
        image = self._cap_image.get()
        ecc   = self._cap_ecc.get()
        enc   = self._cap_enc.get()

        if not audio or not image:
            messagebox.showerror("Missing input", "Please select both files.")
            return

        def task():
            try:
                from capacity import check_fit, max_image_size
                check_fit(audio, image, use_ecc=ecc, encrypted=enc)
                for d in (1, 2, 3):
                    max_image_size(audio, lsb_depth=d, use_ecc=ecc, encrypted=enc)
            except Exception as ex:
                print(f"[ERROR] {ex}")

        self._run_in_thread(task)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = StegoApp()
    app.mainloop()
