import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "load_chat", Path(__file__).with_name("load_chat.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_slow_requests_and_errors_are_not_removed_from_acceptance():
    samples = [{"seconds": 2, "ok": True} for _ in range(95)]
    samples += [{"seconds": 20, "ok": True} for _ in range(5)]
    result = module.summarize(samples, 50)
    assert result["accepted"]
    assert result["p95_seconds"] == 2
    assert result["throughput_requests_per_second"] == 2
    samples[0] = {"seconds": 0.1, "ok": False}
    assert not module.summarize(samples, 50)["accepted"]
    assert module.summarize(samples, 50)["errors"] == 1
    assert module.summarize(samples, 50)["successful_within_10_percent"] == 94


def test_empty_run_never_passes():
    assert not module.summarize([], 0)["accepted"]
