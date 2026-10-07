import os
import subprocess
from pathlib import Path

import pytest


class TestServiceInstallation:
    """Verify service installation replaces stale service links."""

    @pytest.mark.parametrize(
        "script_name",
        ["install-service.sh", "update-service.sh"],
    )
    def test_service_installation_replaces_dangling_service_symlink(
        self,
        tmp_path: Path,
        script_name: str,
    ) -> None:
        """Service installation succeeds when the existing unit is a dangling link."""
        home_directory: Path = tmp_path / "home"
        bin_directory: Path = tmp_path / "bin"
        service_directory: Path = home_directory / ".config/systemd/user"
        service_directory.mkdir(parents=True)
        bin_directory.mkdir()
        service_path: Path = service_directory / "pr-auto-reviewer.service"
        service_path.symlink_to(tmp_path / "missing.service")
        uv_path: Path = bin_directory / "uv"
        uv_path.write_text("#!/usr/bin/env bash\nexit 0\n")
        uv_path.chmod(0o755)
        systemctl_path: Path = bin_directory / "systemctl"
        systemctl_path.write_text(
            "#!/usr/bin/env bash\n"
            "if [ \"$1\" = \"--user\" ] && [ \"$2\" = \"is-enabled\" ]; then\n"
            "    exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        systemctl_path.chmod(0o755)
        environment: dict[str, str] = {
            **os.environ,
            "HOME": str(home_directory),
            "PATH": f"{bin_directory}:{os.environ['PATH']}",
            "SHELL": "/bin/bash",
        }

        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["bash", f"scripts/{script_name}"],
            cwd=Path(__file__).parent.parent,
            env=environment,
            input="y\n",
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert service_path.is_file()
        assert not service_path.is_symlink()
        assert "Description=PR Auto Reviewer" in service_path.read_text()
