"""Comprobar la página desplegada y una consulta real; no se ejecuta en CI."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("/tmp/rag-demo-answer.png"))
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 950})
            page.goto(args.base_url.rstrip("/") + "/demo")
            page.locator("#question").fill("¿Cuál es la nota mínima aprobatoria?")
            page.locator("#submit").click()
            assert page.locator("#submit").is_disabled()
            page.locator("#result").wait_for(state="visible", timeout=150000)
            assert "11" in page.locator("#answer").inner_text()
            assert page.locator("#sources .source").count() > 0
            assert "Reglamento" in page.locator("#sources").inner_text()
            assert page.locator("#submit").is_enabled()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.output), full_page=True)
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "answer": page.locator("#answer").inner_text(),
                        "screenshot": str(args.output),
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
