import importlib.util
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_DIR = Path(__file__).resolve().parent


def find_script(names):
    for name in names:
        path = APP_DIR / name
        if path.exists():
            return path
    return None


ENCODER_NAMES = ["polytrack_encoder.py", "polytrack_encode.py"]
DECODER_NAMES = ["polytrack_decoder.py", "polytrack_decode.py"]


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def try_call_module(module, names, *args):
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args)
    return None


def run_converter(kind, input_path, output_path):
    names = ENCODER_NAMES if kind == "encode" else DECODER_NAMES
    fn_names = (
        ["encode_file", "encode_track", "encode", "json_to_track", "encode_json"]
        if kind == "encode"
        else ["decode_file", "decode_track", "decode", "track_to_json", "decode_track_file"]
    )

    script = find_script(names)
    if not script:
        raise FileNotFoundError(
            "Could not find an encoder/decoder script next to the GUI.\n"
            f"Looked for: {', '.join(names)}"
        )

    # First try importing and calling a common function.
    module = load_module(script)
    result = try_call_module(module, fn_names, str(input_path), str(output_path))
    if result is not None:
        return

    # Fallback to command-line style scripts.
    proc = subprocess.run(
        [sys.executable, str(script), str(input_path), "-o", str(output_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "Unknown converter error."
        raise RuntimeError(detail)


class PolyTrackGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PolyTrack Encoder / Decoder")
        self.geometry("900x680")
        self.minsize(760, 560)

        self.mode = tk.StringVar(value="encode")
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()

        self._build_ui()
        self._update_mode()

    def _build_ui(self):
        # Scrollable application area so the whole UI can be reached
        # even when the window is smaller than the contents.
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(outer, highlightthickness=0)
        self.app_scrollbar = ttk.Scrollbar(
            outer, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.app_scrollbar.set)

        self.app_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )

        def update_scroll_region(event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def resize_scroll_frame(event):
            self.canvas.itemconfigure(self.canvas_window, width=event.width)

        self.scroll_frame.bind("<Configure>", update_scroll_region)
        self.canvas.bind("<Configure>", resize_scroll_frame)

        # Mouse wheel scrolling for the whole app.
        def wheel(event):
            if event.num == 4:       # Linux
                self.canvas.yview_scroll(-3, "units")
            elif event.num == 5:     # Linux
                self.canvas.yview_scroll(3, "units")
            elif event.delta:        # Windows / macOS
                self.canvas.yview_scroll(int(-event.delta / 120), "units")

        self.canvas.bind_all("<MouseWheel>", wheel)
        self.canvas.bind_all("<Button-4>", wheel)
        self.canvas.bind_all("<Button-5>", wheel)

        # All normal app sections live inside the scrollable frame.
        top = ttk.Frame(self.scroll_frame, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Mode:").pack(side="left")
        ttk.Radiobutton(
            top, text="Encode JSON → TRACK", variable=self.mode,
            value="encode", command=self._update_mode
        ).pack(side="left", padx=(8, 4))
        ttk.Radiobutton(
            top, text="Decode TRACK → JSON", variable=self.mode,
            value="decode", command=self._update_mode
        ).pack(side="left", padx=4)

        # Pasted text area
        paste_frame = ttk.LabelFrame(
            self.scroll_frame, text="Paste input text", padding=10
        )
        paste_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.input_text = tk.Text(
            paste_frame, wrap="none", undo=True, font=("TkFixedFont", 10),
            height=16
        )
        self.input_text.pack(side="left", fill="both", expand=True)

        yscroll = ttk.Scrollbar(
            paste_frame, orient="vertical", command=self.input_text.yview
        )
        yscroll.pack(side="right", fill="y")
        self.input_text.configure(yscrollcommand=yscroll.set)

        paste_buttons = ttk.Frame(self.scroll_frame)
        paste_buttons.pack(fill="x", padx=12, pady=(0, 8))

        ttk.Button(
            paste_buttons, text="Paste from Clipboard",
            command=self._paste_clipboard
        ).pack(side="left")
        ttk.Button(
            paste_buttons, text="Clear",
            command=lambda: self.input_text.delete("1.0", "end")
        ).pack(side="left", padx=6)
        ttk.Button(
            paste_buttons, text="Copy Input",
            command=self._copy_input
        ).pack(side="left")

        # File controls
        files = ttk.LabelFrame(
            self.scroll_frame, text="Optional file input/output", padding=10
        )
        files.pack(fill="x", padx=12, pady=(0, 8))

        ttk.Label(files, text="Input file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(files, textvariable=self.input_file).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(files, text="Browse…", command=self._browse_input).grid(
            row=0, column=2
        )

        ttk.Label(files, text="Output file:").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(files, textvariable=self.output_file).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(8, 0)
        )
        ttk.Button(files, text="Save As…", command=self._browse_output).grid(
            row=1, column=2, pady=(8, 0)
        )

        files.columnconfigure(1, weight=1)

        actions = ttk.Frame(self.scroll_frame, padding=(12, 0, 12, 8))
        actions.pack(fill="x")

        self.convert_button = ttk.Button(
            actions, text="Convert", command=self._start_convert
        )
        self.convert_button.pack(side="left")

        ttk.Button(
            actions, text="Load File Into Text",
            command=self._load_file_into_text
        ).pack(side="left", padx=8)

        ttk.Button(
            actions, text="Copy Result",
            command=self._copy_result
        ).pack(side="left")

        # Result
        result_frame = ttk.LabelFrame(
            self.scroll_frame, text="Result / output", padding=10
        )
        result_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.result_text = tk.Text(
            result_frame, wrap="none", undo=False, font=("TkFixedFont", 10),
            height=16
        )
        self.result_text.pack(side="left", fill="both", expand=True)

        rscroll = ttk.Scrollbar(
            result_frame, orient="vertical", command=self.result_text.yview
        )
        rscroll.pack(side="right", fill="y")
        self.result_text.configure(yscrollcommand=rscroll.set)

        status_frame = ttk.Frame(self.scroll_frame, padding=(12, 0, 12, 12))
        status_frame.pack(fill="x")

        self.status = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status).pack(side="left")

    def _update_mode(self):
        if self.mode.get() == "encode":
            self.convert_button.configure(text="Encode JSON → TRACK")
        else:
            self.convert_button.configure(text="Decode TRACK → JSON")

    def _paste_clipboard(self):
        try:
            text = self.clipboard_get()
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", text)
            self.status.set("Pasted clipboard text into input.")
        except tk.TclError:
            messagebox.showerror("Paste", "There is no text available on the clipboard.")

    def _copy_input(self):
        text = self.input_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.set("Input copied to clipboard.")

    def _copy_result(self):
        text = self.result_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.set("Result copied to clipboard.")

    def _browse_input(self):
        if self.mode.get() == "encode":
            types = [("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
        else:
            types = [("TRACK files", "*.track"), ("Text files", "*.txt"), ("All files", "*.*")]
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            self.input_file.set(path)

    def _browse_output(self):
        if self.mode.get() == "encode":
            types = [("TRACK files", "*.track"), ("All files", "*.*")]
            default_ext = ".track"
        else:
            types = [("JSON files", "*.json"), ("All files", "*.*")]
            default_ext = ".json"

        path = filedialog.asksaveasfilename(
            filetypes=types,
            defaultextension=default_ext
        )
        if path:
            self.output_file.set(path)

    def _load_file_into_text(self):
        path = self.input_file.get().strip()
        if not path:
            self._browse_input()
            path = self.input_file.get().strip()
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8")
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", text)
            self.status.set(f"Loaded {Path(path).name} into the paste box.")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _get_input_text(self):
        text = self.input_text.get("1.0", "end-1c")
        if text.strip():
            return text

        path = self.input_file.get().strip()
        if path:
            return Path(path).read_text(encoding="utf-8")

        raise ValueError("Paste input text or choose an input file.")

    def _start_convert(self):
        try:
            raw = self._get_input_text()
        except Exception as e:
            messagebox.showerror("Input error", str(e))
            return

        mode = self.mode.get()
        self.convert_button.configure(state="disabled")
        self.status.set("Converting…")
        self.result_text.delete("1.0", "end")

        threading.Thread(
            target=self._convert_worker,
            args=(mode, raw),
            daemon=True,
        ).start()

    def _convert_worker(self, mode, raw):
        temp_in = None
        temp_out = None
        try:
            # Always give the existing file-based converter a temporary file.
            suffix_in = ".json" if mode == "encode" else ".track"
            suffix_out = ".track" if mode == "encode" else ".json"

            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix_in, delete=False, encoding="utf-8"
            ) as f:
                temp_in = Path(f.name)
                f.write(raw)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix_out, delete=False, encoding="utf-8"
            ) as f:
                temp_out = Path(f.name)

            run_converter(mode, temp_in, temp_out)

            if mode == "encode":
                # TRACK data may contain characters that are still text-safe.
                result = temp_out.read_text(encoding="utf-8")
            else:
                result = temp_out.read_text(encoding="utf-8")

            output_path = self.output_file.get().strip()
            if output_path:
                Path(output_path).write_text(result, encoding="utf-8")

            self.after(0, self._convert_done, result, output_path)
        except Exception as e:
            self.after(0, self._convert_error, str(e))
        finally:
            for p in (temp_in, temp_out):
                if p:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass

    def _convert_done(self, result, output_path):
        self.result_text.insert("1.0", result)
        if output_path:
            self.status.set(f"Done. Saved to {output_path}")
        else:
            self.status.set("Done. Result is shown below.")
        self.convert_button.configure(state="normal")

    def _convert_error(self, error):
        self.status.set("Conversion failed.")
        self.convert_button.configure(state="normal")
        messagebox.showerror("Conversion error", error)


if __name__ == "__main__":
    PolyTrackGUI().mainloop()
