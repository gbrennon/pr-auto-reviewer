class SystemNotifier:
    def notify(self, title: str, message: str) -> None:
        import subprocess
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            timeout=5,
        )

    def notify_error(self, context: str, error: Exception) -> None:
        self.notify(
            "pr-auto-reviewer: ERROR",
            f"{context}: {error}",
        )

    def notify_step(self, step: str, detail: str = "") -> None:
        header = f"pr-auto-reviewer: {step}"
        self.notify(header, detail)