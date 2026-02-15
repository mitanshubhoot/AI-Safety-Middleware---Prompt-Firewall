"""Policy engine for evaluating detection results against policies."""
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.core.models.enums import PolicyAction, Severity
from src.core.models.schemas import Detection
from src.utils.exceptions import PolicyException
from src.utils.logging import get_logger
from src.utils.metrics import policy_evaluations_total

logger = get_logger(__name__)


class PolicyEngine:
    """Engine for evaluating prompts against security policies."""

    def __init__(self, policy_file: Path | str):
        """Initialize policy engine.

        Args:
            policy_file: Path to YAML file containing policies
        """
        self.policy_file = Path(policy_file)
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.allowlist: Dict[str, List[str]] = {}
        self.denylist: Dict[str, List[str]] = {}
        self.default_policy_id: str = "default"
        self._load_policies()

    def _load_policies(self) -> None:
        """Load policies from configuration file."""
        try:
            if not self.policy_file.exists():
                raise PolicyException(
                    f"Policy file not found: {self.policy_file}",
                    {"file": str(self.policy_file)},
                )

            with open(self.policy_file, "r") as f:
                config = yaml.safe_load(f)

            # Load policies
            self.policies = config.get("policies", {})

            # Load settings
            settings = config.get("settings", {})
            self.default_policy_id = settings.get("default_policy", "default")

            # Load allow/deny lists
            self.allowlist = config.get("allowlist", {})
            self.denylist = config.get("denylist", {})

            logger.info(
                "policies_loaded",
                count=len(self.policies),
                default=self.default_policy_id,
            )

        except Exception as e:
            logger.error("failed_to_load_policies", error=str(e))
            raise PolicyException(
                "Failed to load policies",
                {"file": str(self.policy_file), "error": str(e)},
            )

    def get_policy(self, policy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get policy by ID.

        Args:
            policy_id: Policy ID (uses default if None)

        Returns:
            Policy configuration

        Raises:
            PolicyException: If policy not found
        """
        pid = policy_id or self.default_policy_id

        if pid not in self.policies:
            raise PolicyException(
                f"Policy not found: {pid}",
                {"policy_id": pid, "available": list(self.policies.keys())},
            )

        policy = self.policies[pid]

        if not policy.get("enabled", True):
            raise PolicyException(
                f"Policy is disabled: {pid}",
                {"policy_id": pid},
            )

        return policy

    async def evaluate(
        self,
        prompt: str,
        detections: List[Detection],
        policy_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[PolicyAction, str]:
        """Evaluate detections against policy.

        Args:
            prompt: The prompt text
            detections: List of detections from other detectors
            policy_id: Policy ID to use (optional)
            context: Additional context (optional)

        Returns:
            Tuple of (action, reason)
        """
        try:
            policy = self.get_policy(policy_id)
            policy_id_str = policy_id or self.default_policy_id

            # Check denylist first
            if self._check_denylist(prompt):
                action = PolicyAction.BLOCK
                reason = "Prompt contains denied keywords or phrases"
                policy_evaluations_total.labels(
                    policy_id=policy_id_str,
                    action=action.value,
                ).inc()
                logger.info("policy_denied", reason=reason)
                return action, reason

            # Check allowlist
            if self._check_allowlist(prompt):
                action = PolicyAction.ALLOW
                reason = "Prompt matches allowlist"
                policy_evaluations_total.labels(
                    policy_id=policy_id_str,
                    action=action.value,
                ).inc()
                logger.info("policy_allowed", reason=reason)
                return action, reason

            # If no detections, allow by default
            if not detections:
                action = PolicyAction.ALLOW
                reason = "No sensitive data detected"
                policy_evaluations_total.labels(
                    policy_id=policy_id_str,
                    action=action.value,
                ).inc()
                return action, reason

            # Evaluate rules against detections
            action, reason = self._evaluate_rules(policy, detections, context)

            policy_evaluations_total.labels(
                policy_id=policy_id_str,
                action=action.value,
            ).inc()

            logger.debug(
                "policy_evaluated",
                policy_id=policy_id_str,
                action=action.value,
                detections=len(detections),
            )

            return action, reason

        except PolicyException:
            raise
        except Exception as e:
            logger.error("policy_evaluation_failed", error=str(e))
            raise PolicyException(
                "Failed to evaluate policy",
                {"error": str(e)},
            )

    def _check_denylist(self, prompt: str) -> bool:
        """Check if prompt matches denylist.

        Args:
            prompt: Prompt text

        Returns:
            True if matches denylist, False otherwise
        """
        prompt_lower = prompt.lower()

        # Check keywords
        for keyword in self.denylist.get("keywords", []):
            if keyword.lower() in prompt_lower:
                logger.debug("denylist_keyword_matched", keyword=keyword)
                return True

        # Check phrases
        for phrase in self.denylist.get("phrases", []):
            if phrase.lower() in prompt_lower:
                logger.debug("denylist_phrase_matched", phrase=phrase)
                return True

        # Check regex patterns
        import re

        for pattern in self.denylist.get("patterns", []):
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.debug("denylist_pattern_matched", pattern=pattern)
                return True

        return False

    def _check_allowlist(self, prompt: str) -> bool:
        """Check if prompt matches allowlist.

        Args:
            prompt: Prompt text

        Returns:
            True if matches allowlist, False otherwise
        """
        prompt_lower = prompt.lower()

        # Check patterns
        for pattern in self.allowlist.get("patterns", []):
            if pattern.lower() in prompt_lower:
                logger.debug("allowlist_pattern_matched", pattern=pattern)
                return True

        return False

    def _evaluate_rules(
        self,
        policy: Dict[str, Any],
        detections: List[Detection],
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[PolicyAction, str]:
        """Evaluate policy rules against detections.

        Args:
            policy: Policy configuration
            detections: List of detections
            context: Additional context

        Returns:
            Tuple of (action, reason)
        """
        rules = policy.get("rules", [])

        # Track highest severity action
        highest_action = PolicyAction.ALLOW
        reasons: List[str] = []

        for rule in rules:
            if not rule.get("enabled", True):
                continue

            rule_action = PolicyAction(rule.get("action", "warn"))
            rule_categories = rule.get("categories", [])

            # Check if any detection matches this rule
            for detection in detections:
                if not rule_categories or detection.category in rule_categories:
                    # Check severity match
                    rule_severity = rule.get("severity")
                    if rule_severity and detection.severity.value != rule_severity:
                        continue

                    # This detection matches the rule
                    if rule_action == PolicyAction.BLOCK:
                        highest_action = PolicyAction.BLOCK
                        reasons.append(
                            f"Blocked by rule '{rule.get('type')}': "
                            f"{detection.matched_pattern} ({detection.severity.value})"
                        )
                    elif rule_action == PolicyAction.WARN and highest_action != PolicyAction.BLOCK:
                        highest_action = PolicyAction.WARN
                        reasons.append(
                            f"Warning from rule '{rule.get('type')}': "
                            f"{detection.matched_pattern}"
                        )

        if not reasons:
            return PolicyAction.ALLOW, "No policy rules triggered"

        return highest_action, "; ".join(reasons[:3])  # Limit to first 3 reasons

    def reload_policies(self) -> None:
        """Reload policies from configuration file."""
        logger.info("reloading_policies")
        self.policies.clear()
        self.allowlist.clear()
        self.denylist.clear()
        self._load_policies()

    def list_policies(self) -> List[str]:
        """Get list of available policy IDs.

        Returns:
            List of policy IDs
        """
        return list(self.policies.keys())

    def get_policy_info(self, policy_id: str) -> Dict[str, Any]:
        """Get policy information.

        Args:
            policy_id: Policy ID

        Returns:
            Policy information dictionary
        """
        if policy_id not in self.policies:
            raise PolicyException(f"Policy not found: {policy_id}")

        policy = self.policies[policy_id]
        return {
            "id": policy.get("id"),
            "name": policy.get("name"),
            "description": policy.get("description"),
            "version": policy.get("version"),
            "enabled": policy.get("enabled", True),
            "rules_count": len(policy.get("rules", [])),
        }
