"""Bounded browser load on the real Moodle chat; independent cookie jars, no mocks.

Run with the project virtualenv and PLAYWRIGHT_BROWSERS_PATH set. Credentials are
read locally and never included in the report. Ten virtual users reuse the two
student profiles but have distinct sessions; this is not ten distinct students.
"""

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8088"
CHAT = BASE + "/local/acadassistant/index.php"
QUESTIONS = [
    "¿Cuál es la nota mínima aprobatoria?",
    "¿Qué cursos tengo?",
    "¿Qué profesores me enseñan?",
    "¿Cómo solicito orientación psicológica?",
    "Llévame a mi calendario de Moodle",
]


def summarize(samples, elapsed):
    times = sorted(s["seconds"] for s in samples)
    errors = sum(not s["ok"] for s in samples)
    ontime = sum(s["ok"] and s["seconds"] <= 10 for s in samples)
    return {
        "requests": len(samples),
        "errors": errors,
        "error_percent": round(100 * errors / len(samples), 3) if samples else None,
        "successful_within_10_seconds": ontime,
        "successful_within_10_percent": round(100 * ontime / len(samples), 3)
        if samples
        else 0,
        "p95_seconds": times[math.ceil(0.95 * len(times)) - 1] if times else None,
        "median_seconds": statistics.median(times) if times else None,
        "maximum_seconds": max(times) if times else None,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(len(samples) / elapsed, 3)
        if elapsed
        else 0,
        "accepted": bool(samples)
        and errors == 0
        and ontime >= math.ceil(0.95 * len(samples)),
    }


async def main(args):
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".moodle.env").read_text().splitlines()
        if "=" in line
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "complete": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "virtual_users": args.users,
            "rounds": args.rounds,
            "expected_requests": args.users * args.rounds,
            "warmup_requests": args.users,
            "accounts": ["estudiante1", "estudiante2"],
            "independent_browser_contexts": True,
            "questions": QUESTIONS,
            "measurement": "From submit click to new rendered answer; includes Moodle, RAG and remote providers. Login and warmup excluded. Throughput includes between-round resets.",
            "threshold": "At least 95% of all requests successful in <=10s; zero application/transport errors.",
            "retries_by_harness": 0,
        },
        "host": {"platform": platform.platform(), "cpu_count": os.cpu_count()},
        "samples": [],
        "warmup": [],
        "availability_samples": [],
    }

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    async def ask(page, user, turn, question):
        start = time.monotonic()
        answer, error = "", None
        try:
            count = await page.locator(".local-acadassistant-turn").count()
            await page.locator("#assistant-question").fill(question)
            start = time.monotonic()
            await page.get_by_role("button", name="Send question", exact=True).click()
            await page.wait_for_function(
                "document.querySelector('#assistant-form').dataset.submitting === 'false'",
                timeout=150000,
            )
            if await page.locator(".alert-danger,#assistant-error").count():
                error = "application_error"
            elif await page.locator(".local-acadassistant-turn").count() <= count:
                error = "missing_new_answer"
            else:
                answer = (
                    await page.locator(".local-acadassistant-turn")
                    .last.locator(".local-acadassistant-answer")
                    .inner_text()
                )
                if not answer.strip():
                    error = "empty_answer"
        except Exception as exc:
            error = type(exc).__name__
        return {
            "virtual_user": user,
            "round": turn,
            "question": question,
            "seconds": round(time.monotonic() - start, 4),
            "ok": error is None,
            "error": error,
            "answer": answer,
        }

    stop = asyncio.Event()

    def probe():
        outcomes = {}
        for label, url in [
            ("rag", "http://127.0.0.1:8000/health"),
            ("moodle", BASE + "/login/index.php"),
        ]:
            try:
                with urlopen(url, timeout=4) as response:
                    outcomes[label] = response.status == 200
            except Exception:
                outcomes[label] = False
        return outcomes

    async def availability():
        while not stop.is_set():
            report["availability_samples"].append(
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    **await asyncio.to_thread(probe),
                }
            )
            save()
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except TimeoutError:
                pass

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        report["browser"] = browser.version
        pages, contexts = [], []
        monitoring = None
        try:
            # Sequential login avoids confusing authentication load with chat load.
            for user in range(args.users):
                ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
                contexts.append(ctx)
                page = await ctx.new_page()
                await page.goto(BASE + "/login/index.php")
                await page.wait_for_load_state("networkidle")
                await page.locator("#username").fill("estudiante" + str(user % 2 + 1))
                await page.locator("#password").fill(values["MOODLE_DEMO_PASSWORD"])
                await page.locator("#loginbtn").click()
                await page.wait_for_url(lambda url: "/login/" not in url)
                await page.goto(CHAT)
                await page.locator(".local-acadassistant-chat--enhanced").wait_for()
                pages.append(page)
            report["warmup"] = await asyncio.gather(
                *(ask(page, i + 1, 0, QUESTIONS[i % 5]) for i, page in enumerate(pages))
            )
            save()
            if any(not s["ok"] for s in report["warmup"]):
                report["blocked"] = "Warmup failed; measured load not started."
                return 2
            monitoring = asyncio.create_task(availability())
            start = time.monotonic()
            for turn in range(1, args.rounds + 1):

                async def reset(page):
                    await page.get_by_role(
                        "button", name="New conversation", exact=True
                    ).click()
                    await page.wait_for_load_state("networkidle")
                    await page.locator(".local-acadassistant-chat--enhanced").wait_for()

                await asyncio.gather(*(reset(page) for page in pages))
                samples = await asyncio.gather(
                    *(
                        ask(page, i + 1, turn, QUESTIONS[(i + turn - 1) % 5])
                        for i, page in enumerate(pages)
                    )
                )
                report["samples"].extend(samples)
                report["summary"] = summarize(
                    report["samples"], time.monotonic() - start
                )
                save()
                print(
                    f"Round {turn}/{args.rounds}: {sum(s['ok'] for s in samples)}/{args.users} answers; max {max(s['seconds'] for s in samples):.2f}s",
                    flush=True,
                )
            report["complete"] = True
            report["summary"] = summarize(report["samples"], time.monotonic() - start)
            return 0 if report["summary"]["accepted"] else 1
        except Exception as exc:
            report["failure_type"] = type(exc).__name__
            return 2
        finally:
            stop.set()
            if monitoring:
                await monitoring
            probes = report["availability_samples"]
            report["availability"] = {
                "samples": len(probes),
                "interval_seconds": 5,
                "successful_samples": sum(s["rag"] and s["moodle"] for s in probes),
                "percent": round(
                    100 * sum(s["rag"] and s["moodle"] for s in probes) / len(probes), 3
                )
                if probes
                else None,
                "scope": "Sampled HTTP availability during this run only; does not measure long-term uptime or AI answer quality.",
            }
            await browser.close()
            save()
            print(
                json.dumps(
                    report.get(
                        "summary",
                        {
                            "blocked": report.get("blocked"),
                            "failure": report.get("failure_type"),
                        },
                    )
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--rounds", type=int, default=10, choices=range(1, 21))
    parser.add_argument(
        "--output", default=".scratch/cumplimiento-rubrica-final/evidencias/carga.json"
    )
    raise SystemExit(asyncio.run(main(parser.parse_args())))
