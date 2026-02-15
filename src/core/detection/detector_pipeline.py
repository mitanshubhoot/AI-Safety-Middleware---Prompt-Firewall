"""Detector pipeline that orchestrates all detection components."""
import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional

from src.config import get_settings
from src.core.cache.redis_client import RedisClient, get_redis_client
from src.core.detection.policy_engine import PolicyEngine
from src.core.detection.regex_detector import RegexDetector
from src.core.detection.semantic_detector import SemanticDetector
from src.core.models.enums import PolicyAction, ValidationStatus
from src.core.models.schemas import Detection, ValidationResult
from src.utils.exceptions import ValidationException
from src.utils.logging import get_logger
from src.utils.metrics import detections_by_type, prompt_validation_duration_seconds, prompt_validation_total

logger = get_logger(__name__)
settings = get_settings()


class DetectorPipeline:
    """Pipeline that runs all detectors in parallel and evaluates results."""

    def __init__(
        self,
        regex_detector: Optional[RegexDetector] = None,
        semantic_detector: Optional[SemanticDetector] = None,
        policy_engine: Optional[PolicyEngine] = None,
        cache_client: Optional[RedisClient] = None,
    ):
        """Initialize detector pipeline.

        Args:
            regex_detector: Regex detector instance (optional)
            semantic_detector: Semantic detector instance (optional)
            policy_engine: Policy engine instance (optional)
            cache_client: Redis cache client (optional)
        """
        # Initialize detectors
        self.regex_detector = regex_detector or RegexDetector(settings.REGEX_PATTERNS_FILE)
        self.semantic_detector = semantic_detector or SemanticDetector()
        self.policy_engine = policy_engine or PolicyEngine(settings.POLICY_CONFIG_FILE)
        self._cache_client = cache_client
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the pipeline components."""
        if self._initialized:
            return

        logger.info("initializing_detector_pipeline")

        # Initialize semantic detector
        await self.semantic_detector.initialize()

        # Initialize cache client
        if self._cache_client is None and settings.ENABLE_CACHE:
            self._cache_client = await get_redis_client()

        self._initialized = True
        logger.info("detector_pipeline_initialized")

    async def validate(
        self,
        prompt: str,
        user_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate prompt through detection pipeline.

        Args:
            prompt: The prompt text to validate
            user_id: User ID for audit logging (optional)
            policy_id: Policy ID to use (optional)
            context: Additional context (optional)

        Returns:
            ValidationResult with detections and policy decision
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        request_id_str = hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:16]

        try:
            # Check cache first
            cached_result = None
            if self._cache_client and settings.ENABLE_CACHE:
                policy_id_for_cache = policy_id or self.policy_engine.default_policy_id
                cached_result = await self._cache_client.get_cached_validation(
                    prompt, policy_id_for_cache
                )

            if cached_result:
                # Return cached result
                latency_ms = (time.time() - start_time) * 1000
                logger.info("validation_from_cache", latency_ms=latency_ms)

                # Update metrics
                prompt_validation_total.labels(
                    status=cached_result["status"],
                    policy=policy_id or "default",
                ).inc()

                return ValidationResult(**cached_result, cached=True, latency_ms=latency_ms)

            # Run all detectors in parallel
            detection_results = await asyncio.gather(
                self.regex_detector.check(prompt),
                self.semantic_detector.check(prompt),
                return_exceptions=True,
            )

            # Collect all detections
            all_detections: List[Detection] = []

            # Process regex results
            if isinstance(detection_results[0], list):
                all_detections.extend(detection_results[0])
            elif isinstance(detection_results[0], Exception):
                logger.error(
                    "regex_detection_failed",
                    error=str(detection_results[0]),
                )

            # Process semantic results
            if isinstance(detection_results[1], list):
                all_detections.extend(detection_results[1])
            elif isinstance(detection_results[1], Exception):
                logger.error(
                    "semantic_detection_failed",
                    error=str(detection_results[1]),
                )

            # Evaluate policy
            policy_action, policy_reason = await self.policy_engine.evaluate(
                prompt=prompt,
                detections=all_detections,
                policy_id=policy_id,
                context=context,
            )

            # Determine validation status
            if policy_action == PolicyAction.BLOCK:
                status = ValidationStatus.BLOCKED
                is_safe = False
            elif policy_action == PolicyAction.WARN:
                status = ValidationStatus.WARNED
                is_safe = True
            else:
                status = ValidationStatus.ALLOWED
                is_safe = True

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Create validation result
            result = ValidationResult(
                status=status,
                is_safe=is_safe,
                detections=all_detections,
                policy_id=policy_id or self.policy_engine.default_policy_id,
                latency_ms=latency_ms,
                message=policy_reason,
                cached=False,
            )

            # Update metrics
            prompt_validation_total.labels(
                status=status.value,
                policy=result.policy_id,
            ).inc()

            prompt_validation_duration_seconds.labels(
                policy=result.policy_id,
            ).observe(latency_ms / 1000)

            # Record detections by type
            for detection in all_detections:
                detections_by_type.labels(
                    detection_type=detection.detection_type.value,
                    severity=detection.severity.value,
                    blocked=str(not is_safe).lower(),
                ).inc()

            # Cache result if enabled
            if self._cache_client and settings.ENABLE_CACHE and is_safe:
                # Only cache safe results
                await self._cache_client.cache_validation(
                    prompt=prompt,
                    policy_id=result.policy_id,
                    result=result.model_dump(mode="json"),
                )

            logger.info(
                "validation_completed",
                status=status.value,
                detections=len(all_detections),
                latency_ms=latency_ms,
                policy_id=result.policy_id,
                user_id=user_id,
            )

            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "validation_failed",
                error=str(e),
                latency_ms=latency_ms,
            )

            prompt_validation_total.labels(
                status="error",
                policy=policy_id or "default",
            ).inc()

            raise ValidationException(
                "Validation failed",
                {
                    "error": str(e),
                    "latency_ms": latency_ms,
                    "user_id": user_id,
                },
            )

    async def batch_validate(
        self,
        prompts: List[tuple[str, Optional[str], Optional[str], Optional[Dict[str, Any]]]],
    ) -> List[ValidationResult]:
        """Validate multiple prompts in parallel.

        Args:
            prompts: List of (prompt, user_id, policy_id, context) tuples

        Returns:
            List of ValidationResult objects
        """
        if not self._initialized:
            await self.initialize()

        logger.info("batch_validation_started", count=len(prompts))

        # Run validations in parallel
        tasks = [
            self.validate(prompt, user_id, policy_id, context)
            for prompt, user_id, policy_id, context in prompts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        validated_results: List[ValidationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "batch_validation_item_failed",
                    index=i,
                    error=str(result),
                )
                # Create error result
                validated_results.append(
                    ValidationResult(
                        status=ValidationStatus.ERROR,
                        is_safe=False,
                        detections=[],
                        policy_id="default",
                        latency_ms=0,
                        message=f"Validation error: {str(result)}",
                        cached=False,
                    )
                )
            else:
                validated_results.append(result)

        logger.info("batch_validation_completed", count=len(validated_results))
        return validated_results

    def reload_detectors(self) -> None:
        """Reload all detector configurations."""
        logger.info("reloading_detectors")
        self.regex_detector.reload_patterns()
        self.policy_engine.reload_policies()
        logger.info("detectors_reloaded")

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Dictionary with pipeline statistics
        """
        return {
            "regex_categories": self.regex_detector.get_pattern_categories(),
            "policies": self.policy_engine.list_policies(),
            "cache_enabled": settings.ENABLE_CACHE,
            "semantic_threshold": self.semantic_detector.threshold,
        }


# Global pipeline instance
_pipeline: Optional[DetectorPipeline] = None


async def get_detector_pipeline() -> DetectorPipeline:
    """Get or create global detector pipeline instance.

    Returns:
        DetectorPipeline instance
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = DetectorPipeline()
        await _pipeline.initialize()
    return _pipeline
