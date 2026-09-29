from .base import AgentPermissions, BaseAgent

STATUSES = {"VERIFIED", "PARTIALLY_VERIFIED", "UNSUPPORTED", "CONTRADICTED", "REQUIRES_HUMAN_REVIEW"}
NEGATION_MARKERS = ("not ", "no evidence", "contrary", "however", "unconfirmed", "disputed")


class VerificationAgent(BaseAgent):
    name = "Verification Agent"
    description = "Independently checks every finding against supporting and contradictory evidence"
    permissions = AgentPermissions(
        allowed_tools=["evidence.verify"],
        allowed_data_sources=["retrieved_evidence", "agent_findings"],
    )

    def verify_finding(self, finding: dict, evidence: list[dict]) -> dict:
        statement = finding.get("statement", "")
        tokens = {word.strip(".,:;()").lower() for word in statement.split() if len(word) > 4}
        supporting: list[dict] = []
        contradictory: list[dict] = []
        for item in evidence:
            text = item.get("excerpt", "").lower()
            overlap = sum(1 for token in tokens if token in text)
            if any(marker in text for marker in NEGATION_MARKERS) and overlap:
                contradictory.append(item)
            elif overlap >= 2 or item.get("relevance_score", 0) >= 0.45:
                supporting.append(item)
        high = finding.get("risk_level") in {"HIGH", "CRITICAL"}
        if contradictory and not supporting:
            status, confidence = "CONTRADICTED", 0.82
        elif not supporting:
            status, confidence = "UNSUPPORTED", 0.95
        elif contradictory:
            status, confidence = "PARTIALLY_VERIFIED", 0.58
        elif high:
            status, confidence = "REQUIRES_HUMAN_REVIEW", 0.8
        else:
            status, confidence = "VERIFIED", 0.9
        return {
            "finding": statement,
            "status": status,
            "supporting_evidence": supporting,
            "contradictory_evidence": contradictory,
            "confidence": confidence,
            "risk_level": finding.get("risk_level", "MEDIUM"),
            "human_review_recommended": high or status != "VERIFIED",
        }

    def execute(self, task_id: int, description: str, context: dict):
        evidence = list(context.get("evidence", []))
        findings = list(context.get("findings", []))
        results = [self.verify_finding(finding, evidence) for finding in findings]
        confidence = min((item["confidence"] for item in results), default=0.0)
        counts = {status: 0 for status in sorted(STATUSES)}
        for item in results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        actions = [
            "matched each claim to retrieved passages",
            "checked for contradictory passages",
            "assigned an explicit verification status per finding",
        ]
        return self.result(
            task_id,
            "COMPLETED",
            f"Compared {len(results)} finding(s) with {len(evidence)} passage(s); "
            f"unsupported claims stay excluded from the final response.",
            actions,
            evidence,
            {
                "verification_results": results,
                "summary": counts,
                "verified_count": counts.get("VERIFIED", 0),
            },
            confidence,
        )
