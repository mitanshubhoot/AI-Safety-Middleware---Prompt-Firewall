"""Unit tests for regex detector."""
import pytest

from src.core.detection.regex_detector import RegexDetector
from src.core.models.enums import DetectionType, Severity


@pytest.fixture
def detector():
    """Create regex detector instance."""
    return RegexDetector("./config/patterns.yaml")


@pytest.mark.asyncio
async def test_detect_openai_api_key(detector):
    """Test detection of OpenAI API key."""
    prompt = "My API key is sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
    detections = await detector.check(prompt)
    
    assert len(detections) > 0
    assert detections[0].detection_type == DetectionType.REGEX
    assert detections[0].matched_pattern == "openai_api_key"
    assert detections[0].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_detect_ssn(detector):
    """Test detection of Social Security Number."""
    prompt = "My SSN is 123-45-6789"
    detections = await detector.check(prompt)
    
    assert len(detections) > 0
    assert any(d.matched_pattern == "ssn" for d in detections)


@pytest.mark.asyncio
async def test_detect_credit_card(detector):
    """Test detection of credit card number."""
    prompt = "My card is 4532-1234-5678-9010"
    detections = await detector.check(prompt)
    
    assert len(detections) > 0
    assert any(d.category == "pii" for d in detections)


@pytest.mark.asyncio
async def test_no_detection_safe_prompt(detector):
    """Test no detection on safe prompt."""
    prompt = "What is the capital of France?"
    detections = await detector.check(prompt)
    
    assert len(detections) == 0


@pytest.mark.asyncio
async def test_contextual_pattern(detector):
    """Test contextual pattern detection."""
    prompt = "The password is SuperSecret123"
    detections = await detector.check(prompt)
    
    # Should detect contextual pattern
    assert len(detections) > 0
