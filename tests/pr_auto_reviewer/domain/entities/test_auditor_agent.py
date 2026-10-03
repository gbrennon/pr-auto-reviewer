from pr_auto_reviewer.domain.entities.auditor_agent import AuditorAgent
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole


class TestAuditorAgent:
    """The auditor role proves whether prior findings were remediated."""

    def test_role_identity(self) -> None:
        assert SubAgentRole.AUDITOR == "auditor"
        assert AuditorAgent().role == "auditor"

    def test_behavior_demands_proof_of_remediation(self) -> None:
        text = (AuditorAgent().responsibility + AuditorAgent().behavior).lower()
        assert "prove" in text or "proof" in text
        assert "prior" in text or "previous" in text
