"""Regex-based pattern detector for sensitive data."""
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.core.models.enums import DetectionType, Severity
from src.core.models.schemas import Detection
from src.utils.exceptions import DetectionException
from src.utils.logging import get_logger
from src.utils.metrics import regex_detections_total

logger = get_logger(__name__)


class RegexDetector:
    """Detector for sensitive data using regex patterns."""

    def __init__(self, patterns_file: Path | str):
        """Initialize regex detector with patterns from YAML file.

        Args:
            patterns_file: Path to YAML file containing regex patterns
        """
        self.patterns_file = Path(patterns_file)
        self.compiled_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.contextual_patterns: List[Dict[str, Any]] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load and compile regex patterns from configuration file."""
        try:
            if not self.patterns_file.exists():
                raise DetectionException(
                    f"Patterns file not found: {self.patterns_file}",
                    {"file": str(self.patterns_file)},
                )

            with open(self.patterns_file, "r") as f:
                config = yaml.safe_load(f)

            patterns_config = config.get("patterns", {})

            # Compile patterns by category
            for category, patterns in patterns_config.items():
                self.compiled_patterns[category] = []
                for pattern_def in patterns:
                    try:
                        compiled = re.compile(pattern_def["pattern"], re.IGNORECASE)
                        self.compiled_patterns[category].append(
                            {
                                "name": pattern_def["name"],
                                "compiled": compiled,
                                "description": pattern_def["description"],
                                "severity": pattern_def["severity"],
                                "category": category,
                            }
                        )
                    except re.error as e:
                        logger.warning(
                            "invalid_regex_pattern",
                            pattern=pattern_def["name"],
                            error=str(e),
                        )

            # Load contextual patterns
            self.contextual_patterns = config.get("contextual_patterns", [])

            logger.info(
                "regex_patterns_loaded",
                categories=len(self.compiled_patterns),
                total_patterns=sum(len(p) for p in self.compiled_patterns.values()),
            )

        except Exception as e:
            logger.error("failed_to_load_patterns", error=str(e))
            raise DetectionException(
                "Failed to load regex patterns",
                {"file": str(self.patterns_file), "error": str(e)},
            )

    async def check(self, prompt: str) -> List[Detection]:
        """Check prompt for sensitive data using regex patterns.

        Args:
            prompt: The prompt text to check

        Returns:
            List of Detection objects for any matches found
        """
        detections: List[Detection] = []

        # Check all compiled patterns
        for category, patterns in self.compiled_patterns.items():
            for pattern_def in patterns:
                matches = list(pattern_def["compiled"].finditer(prompt))
                if matches:
                    # Get match positions
                    match_positions = [(m.start(), m.end()) for m in matches]

                    detection = Detection(
                        detection_type=DetectionType.REGEX,
                        matched_pattern=pattern_def["name"],
                        confidence_score=1.0,  # Regex matches are exact
                        severity=Severity(pattern_def["severity"]),
                        category=category,
                        match_positions=match_positions,
                        metadata={
                            "description": pattern_def["description"],
                            "match_count": len(matches),
                            "matched_text": [m.group() for m in matches[:3]],  # First 3 matches
                        },
                    )
                    detections.append(detection)

                    # Record metrics
                    regex_detections_total.labels(
                        pattern_name=pattern_def["name"],
                        category=category,
                    ).inc()

                    logger.debug(
                        "regex_match_found",
                        pattern=pattern_def["name"],
                        category=category,
                        matches=len(matches),
                    )

        # Check contextual patterns
        contextual_detections = self._check_contextual_patterns(prompt)
        detections.extend(contextual_detections)

        return detections

    def _check_contextual_patterns(self, prompt: str) -> List[Detection]:
        """Check for contextual patterns (e.g., 'password is...').

        Args:
            prompt: The prompt text to check

        Returns:
            List of Detection objects for contextual matches
        """
        detections: List[Detection] = []
        prompt_lower = prompt.lower()

        for ctx_pattern in self.contextual_patterns:
            trigger = ctx_pattern["trigger"].lower()
            if trigger in prompt_lower:
                # Find the position of the trigger
                idx = prompt_lower.find(trigger)
                # Extract surrounding context (50 chars after trigger)
                context_start = idx
                context_end = min(idx + len(trigger) + 50, len(prompt))
                context_text = prompt[context_start:context_end]

                detection = Detection(
                    detection_type=DetectionType.CONTEXTUAL,
                    matched_pattern=trigger,
                    confidence_score=0.8,  # Contextual matches are less certain
                    severity=Severity(ctx_pattern["severity"]),
                    category="contextual",
                    match_positions=[(idx, idx + len(trigger))],
                    metadata={
                        "trigger": trigger,
                        "context": context_text,
                        "description": f"Contextual pattern detected: {trigger}",
                    },
                )
                detections.append(detection)

                logger.debug(
                    "contextual_pattern_found",
                    trigger=trigger,
                    position=idx,
                )

        return detections

    def reload_patterns(self) -> None:
        """Reload patterns from configuration file."""
        logger.info("reloading_regex_patterns")
        self.compiled_patterns.clear()
        self.contextual_patterns.clear()
        self._load_patterns()

    def get_pattern_categories(self) -> List[str]:
        """Get list of available pattern categories.

        Returns:
            List of category names
        """
        return list(self.compiled_patterns.keys())

    def get_patterns_in_category(self, category: str) -> List[str]:
        """Get list of pattern names in a specific category.

        Args:
            category: Category name

        Returns:
            List of pattern names
        """
        if category not in self.compiled_patterns:
            return []
        return [p["name"] for p in self.compiled_patterns[category]]
