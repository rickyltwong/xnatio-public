"""
Legacy reference: retained for future GUI work; not wired into xnatio.

Graphical user interface for XNATIO Uploader.

Uses tkinter for cross-platform compatibility.
"""

import os
import sys
import threading
import queue
from pathlib import Path
from tkinter import (
    Tk, ttk, StringVar, BooleanVar,
    filedialog, messagebox,
    N, S, E, W, HORIZONTAL, DISABLED, NORMAL, END,
)
from tkinter.scrolledtext import ScrolledText

from . import __version__
from .config import load_config, find_env_file, XNATConfig
from .uploader import upload_session, UploadProgress
from .defaults import DEFAULT_XNAT_SITE


class XNATIOUploaderGUI:
    """Main GUI application."""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title(f"XNATIO Uploader v{__version__}")
        self.root.minsize(500, 600)

        # Message queue for thread-safe updates
        self.msg_queue = queue.Queue()

        # Variables
        self.source_dir = StringVar()
        self.project = StringVar()
        self.subject = StringVar()
        self.session = StringVar()
        self.xnat_site = StringVar(value=DEFAULT_XNAT_SITE)
        self.username = StringVar()
        self.password = StringVar()
        self.progress_var = StringVar(value="Ready")
        self.progress_pct = 0
        self.uploading = BooleanVar(value=False)

        # Load config
        self._load_config()

        # Build UI
        self._build_ui()

        # Start message processor
        self._process_messages()

    def _load_config(self):
        """Load configuration from .env file."""
        env_file = find_env_file()
        config = load_config()

        if config.site:
            self.xnat_site.set(config.site)
        if config.username:
            self.username.set(config.username)
        if config.password:
            self.password.set(config.password)

    def _build_ui(self):
        """Build the user interface."""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(N, S, E, W))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # Title
        title = ttk.Label(
            main_frame,
            text="XNATIO Uploader",
            font=("TkDefaultFont", 16, "bold"),
        )
        title.grid(row=row, column=0, columnspan=3, pady=(0, 10))
        row += 1

        # Source directory section
        section_label = ttk.Label(main_frame, text="DICOM Source", font=("TkDefaultFont", 10, "bold"))
        section_label.grid(row=row, column=0, columnspan=3, sticky=W, pady=(10, 5))
        row += 1

        ttk.Label(main_frame, text="Directory:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        source_entry = ttk.Entry(main_frame, textvariable=self.source_dir, width=40)
        source_entry.grid(row=row, column=1, sticky=(E, W))
        ttk.Button(main_frame, text="Browse...", command=self._browse_source).grid(
            row=row, column=2, padx=(5, 0)
        )
        row += 1

        # XNAT Target section
        section_label = ttk.Label(main_frame, text="XNAT Target", font=("TkDefaultFont", 10, "bold"))
        section_label.grid(row=row, column=0, columnspan=3, sticky=W, pady=(15, 5))
        row += 1

        ttk.Label(main_frame, text="Project:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.project).grid(row=row, column=1, sticky=(E, W))
        row += 1

        ttk.Label(main_frame, text="Subject:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.subject).grid(row=row, column=1, sticky=(E, W))
        row += 1

        ttk.Label(main_frame, text="Session:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.session).grid(row=row, column=1, sticky=(E, W))
        row += 1

        # Credentials section
        section_label = ttk.Label(main_frame, text="XNAT Credentials", font=("TkDefaultFont", 10, "bold"))
        section_label.grid(row=row, column=0, columnspan=3, sticky=W, pady=(15, 5))
        row += 1

        ttk.Label(main_frame, text="Site URL:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.xnat_site).grid(row=row, column=1, sticky=(E, W))
        row += 1

        ttk.Label(main_frame, text="Username:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.username).grid(row=row, column=1, sticky=(E, W))
        row += 1

        ttk.Label(main_frame, text="Password:").grid(row=row, column=0, sticky=E, padx=(0, 5))
        ttk.Entry(main_frame, textvariable=self.password, show="*").grid(
            row=row, column=1, sticky=(E, W)
        )
        row += 1

        # Progress section
        section_label = ttk.Label(main_frame, text="Progress", font=("TkDefaultFont", 10, "bold"))
        section_label.grid(row=row, column=0, columnspan=3, sticky=W, pady=(15, 5))
        row += 1

        self.progress_bar = ttk.Progressbar(
            main_frame, orient=HORIZONTAL, mode="determinate", length=400
        )
        self.progress_bar.grid(row=row, column=0, columnspan=3, sticky=(E, W), pady=(0, 5))
        row += 1

        progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        progress_label.grid(row=row, column=0, columnspan=3, sticky=W)
        row += 1

        # Log section
        section_label = ttk.Label(main_frame, text="Log", font=("TkDefaultFont", 10, "bold"))
        section_label.grid(row=row, column=0, columnspan=3, sticky=W, pady=(15, 5))
        row += 1

        self.log_text = ScrolledText(main_frame, height=10, state=DISABLED)
        self.log_text.grid(row=row, column=0, columnspan=3, sticky=(N, S, E, W))
        main_frame.rowconfigure(row, weight=1)
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(15, 0))

        self.upload_btn = ttk.Button(
            button_frame, text="Upload", command=self._start_upload, width=15
        )
        self.upload_btn.pack(side="left", padx=5)

        ttk.Button(button_frame, text="Clear Log", command=self._clear_log, width=15).pack(
            side="left", padx=5
        )

        ttk.Button(button_frame, text="Quit", command=self.root.quit, width=15).pack(
            side="left", padx=5
        )

    def _browse_source(self):
        """Open directory browser."""
        directory = filedialog.askdirectory(title="Select DICOM Directory")
        if directory:
            self.source_dir.set(directory)
            self._log(f"Selected: {directory}")

    def _log(self, message: str):
        """Add message to log."""
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def _clear_log(self):
        """Clear the log."""
        self.log_text.config(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.config(state=DISABLED)

    def _validate_inputs(self) -> bool:
        """Validate all inputs before upload."""
        errors = []

        if not self.source_dir.get():
            errors.append("Please select a DICOM directory")
        elif not Path(self.source_dir.get()).exists():
            errors.append("Selected directory does not exist")

        if not self.project.get():
            errors.append("Please enter a project ID")
        if not self.subject.get():
            errors.append("Please enter a subject label")
        if not self.session.get():
            errors.append("Please enter a session label")

        if not self.xnat_site.get():
            errors.append("Please enter the XNAT site URL")
        if not self.username.get():
            errors.append("Please enter your username")
        if not self.password.get():
            errors.append("Please enter your password")

        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False

        return True

    def _start_upload(self):
        """Start the upload in a background thread."""
        if self.uploading.get():
            return

        if not self._validate_inputs():
            return

        self.uploading.set(True)
        self.upload_btn.config(state=DISABLED)
        self.progress_bar["value"] = 0
        self.progress_var.set("Starting upload...")
        self._log("=" * 40)
        self._log("Starting upload...")

        # Create config
        config = XNATConfig(
            site=self.xnat_site.get(),
            username=self.username.get(),
            password=self.password.get(),
        )

        # Start upload thread
        thread = threading.Thread(
            target=self._upload_thread,
            args=(
                config,
                self.source_dir.get(),
                self.project.get(),
                self.subject.get(),
                self.session.get(),
            ),
            daemon=True,
        )
        thread.start()

    def _upload_thread(
        self,
        config: XNATConfig,
        source_dir: str,
        project: str,
        subject: str,
        session: str,
    ):
        """Background upload thread."""
        try:
            summary = upload_session(
                config=config,
                source_dir=source_dir,
                project=project,
                subject=subject,
                session=session,
                progress_callback=lambda p: self.msg_queue.put(("progress", p)),
            )

            self.msg_queue.put(("complete", summary))

        except Exception as e:
            self.msg_queue.put(("error", str(e)))

    def _process_messages(self):
        """Process messages from the upload thread."""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == "progress":
                    self._handle_progress(data)
                elif msg_type == "complete":
                    self._handle_complete(data)
                elif msg_type == "error":
                    self._handle_error(data)

        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self._process_messages)

    def _handle_progress(self, progress: UploadProgress):
        """Handle progress update."""
        self.progress_var.set(progress.message)

        if progress.total > 0:
            pct = int(progress.current / progress.total * 100)
            self.progress_bar["value"] = pct

        if progress.phase in ("scanning", "archiving", "uploading"):
            if progress.current > 0 and progress.current == progress.total:
                self._log(f"  {progress.message}")
            elif progress.total == 0:
                self._log(f"  {progress.message}")

    def _handle_complete(self, summary):
        """Handle upload complete."""
        self.uploading.set(False)
        self.upload_btn.config(state=NORMAL)
        self.progress_bar["value"] = 100

        self._log("=" * 40)
        self._log(f"Files: {summary.total_files}")
        self._log(f"Size: {summary.total_size_mb:.1f} MB")
        self._log(f"Duration: {summary.duration:.1f}s")
        self._log(f"Batches: {summary.batches_succeeded} succeeded, {summary.batches_failed} failed")

        if summary.success:
            self.progress_var.set("Upload completed successfully!")
            self._log("\nUpload completed successfully!")
            messagebox.showinfo("Success", "Upload completed successfully!")
        else:
            self.progress_var.set("Upload completed with errors")
            self._log("\nUpload completed with errors:")
            for error in summary.errors[:5]:
                self._log(f"  - {error}")
            messagebox.showwarning(
                "Completed with Errors",
                f"Upload completed with {summary.batches_failed} batch failures.\nSee log for details.",
            )

    def _handle_error(self, error: str):
        """Handle upload error."""
        self.uploading.set(False)
        self.upload_btn.config(state=NORMAL)
        self.progress_var.set("Upload failed")
        self._log(f"\nError: {error}")
        messagebox.showerror("Upload Failed", error)


def run_gui():
    """Launch the GUI application."""
    root = Tk()

    # Set icon if available (will fail silently if not)
    try:
        # On Windows, you could use .ico file
        # On Linux/Mac, this might not work
        pass
    except Exception:
        pass

    app = XNATIOUploaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
