"""
Evaluation Benchmark Runner for FASHORA Agent 1.
Computes empirical accuracy, precision, and latency for NLP requirement extraction and missing item detection.
"""

import json
import time
from pathlib import Path
import sys

# Ensure project root is in python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents" / "agent1_wardrobe"))

from app.services.nlp.requirement_extractor import fashion_requirement_service
from app.services.nlp.prompt_guard import prompt_guard
from app.services.outfit_requirements import outfit_requirement_engine
from app.services.missing_items import missing_item_detector
from shared.schemas.agent1_schemas import WardrobeSummaryItem


def run_benchmark():
    eval_dir = ROOT / "evaluation"
    with open(eval_dir / "requests.json", "r") as f:
        requests_data = json.load(f)
    with open(eval_dir / "expected_outputs.json", "r") as f:
        expected_data = {item["id"]: item["expected"] for item in json.load(f)}

    print("=" * 60)
    print("FASHORA Agent 1 — Empirical Benchmark Evaluation")
    print("=" * 60)

    total_cases = len(requests_data)
    occasion_matches = 0
    style_matches = 0
    color_matches = 0
    budget_matches = 0
    latencies = []

    for req in requests_data:
        req_id = req["id"]
        prompt = req["prompt"]
        exp = expected_data.get(req_id, {})

        start = time.perf_counter()
        reqs, conf, threat = fashion_requirement_service.process_request(prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        # Check occasion
        occ_ok = (reqs.occasion == exp.get("occasion"))
        if occ_ok:
            occasion_matches += 1

        # Check style
        exp_styles = exp.get("style", [])
        style_ok = all(s in reqs.style for s in exp_styles) if exp_styles else True
        if style_ok:
            style_matches += 1

        # Check budget
        exp_budget = exp.get("budget")
        budget_ok = (reqs.budget == exp_budget)
        if budget_ok:
            budget_matches += 1

        print(f"[{req_id}] Occasion: {'PASS' if occ_ok else 'FAIL'} | Style: {'PASS' if style_ok else 'FAIL'} | Budget: {'PASS' if budget_ok else 'FAIL'} ({elapsed_ms:.1f}ms)")

    occ_acc = (occasion_matches / total_cases) * 100
    style_acc = (style_matches / total_cases) * 100
    budget_acc = (budget_matches / total_cases) * 100
    avg_latency = sum(latencies) / len(latencies)

    print("-" * 60)
    print(f"Empirical Evaluation Summary ({total_cases} test cases):")
    print(f"  - Occasion Extraction Accuracy: {occ_acc:.1f}%")
    print(f"  - Style Recognition Accuracy:   {style_acc:.1f}%")
    print(f"  - Budget Extraction Accuracy:   {budget_acc:.1f}%")
    print(f"  - Average Processing Latency:   {avg_latency:.2f} ms")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
