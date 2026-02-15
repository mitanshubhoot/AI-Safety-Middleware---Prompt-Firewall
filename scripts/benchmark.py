"""Benchmark script for performance testing."""
import asyncio
import time
from statistics import mean, median, stdev
from typing import List

from src.config import get_settings
from src.core.detection.detector_pipeline import DetectorPipeline
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

# Test prompts
SAFE_PROMPTS = [
    "What is the capital of France?",
    "Explain how photosynthesis works.",
    "Write a Python function to calculate factorial.",
    "What are the benefits of exercise?",
    "Describe the water cycle.",
]

UNSAFE_PROMPTS = [
    "My API key is sk-1234567890abcdefghijklmnopqrstuvwxyz123456",
    "Use this card: 4532-1234-5678-9010 CVV: 123",
    "My SSN is 123-45-6789 and password is Admin123!",
    "Here's my AWS access key: AKIAIOSFODNN7EXAMPLE",
    "The private key is -----BEGIN RSA PRIVATE KEY-----",
]


async def benchmark_single_validation(pipeline: DetectorPipeline, prompt: str) -> float:
    """Benchmark single validation.

    Args:
        pipeline: Detector pipeline
        prompt: Prompt to validate

    Returns:
        Latency in milliseconds
    """
    start = time.time()
    await pipeline.validate(prompt)
    return (time.time() - start) * 1000


async def run_benchmarks() -> None:
    """Run performance benchmarks."""
    logger.info("starting_benchmarks")

    # Initialize pipeline
    pipeline = DetectorPipeline()
    await pipeline.initialize()

    # Warm up
    logger.info("warming_up")
    for prompt in SAFE_PROMPTS[:2]:
        await pipeline.validate(prompt)

    # Benchmark safe prompts
    logger.info("benchmarking_safe_prompts")
    safe_latencies: List[float] = []

    for _ in range(10):
        for prompt in SAFE_PROMPTS:
            latency = await benchmark_single_validation(pipeline, prompt)
            safe_latencies.append(latency)

    # Benchmark unsafe prompts
    logger.info("benchmarking_unsafe_prompts")
    unsafe_latencies: List[float] = []

    for _ in range(10):
        for prompt in UNSAFE_PROMPTS:
            latency = await benchmark_single_validation(pipeline, prompt)
            unsafe_latencies.append(latency)

    # Calculate statistics
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    print("\nSafe Prompts:")
    print(f"  Total validations: {len(safe_latencies)}")
    print(f"  Mean latency: {mean(safe_latencies):.2f}ms")
    print(f"  Median latency: {median(safe_latencies):.2f}ms")
    print(f"  Std deviation: {stdev(safe_latencies):.2f}ms")
    print(f"  Min latency: {min(safe_latencies):.2f}ms")
    print(f"  Max latency: {max(safe_latencies):.2f}ms")

    print("\nUnsafe Prompts:")
    print(f"  Total validations: {len(unsafe_latencies)}")
    print(f"  Mean latency: {mean(unsafe_latencies):.2f}ms")
    print(f"  Median latency: {median(unsafe_latencies):.2f}ms")
    print(f"  Std deviation: {stdev(unsafe_latencies):.2f}ms")
    print(f"  Min latency: {min(unsafe_latencies):.2f}ms")
    print(f"  Max latency: {max(unsafe_latencies):.2f}ms")

    # Calculate throughput
    total_prompts = len(safe_latencies) + len(unsafe_latencies)
    total_time = (sum(safe_latencies) + sum(unsafe_latencies)) / 1000
    throughput = total_prompts / total_time

    print("\nThroughput:")
    print(f"  {throughput:.2f} prompts/second")
    print(f"  {throughput * 60:.2f} prompts/minute")
    print(f"  {throughput * 3600:.2f} prompts/hour")

    print("\n" + "=" * 60)

    logger.info(
        "benchmarks_completed",
        safe_mean=mean(safe_latencies),
        unsafe_mean=mean(unsafe_latencies),
        throughput=throughput,
    )


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
