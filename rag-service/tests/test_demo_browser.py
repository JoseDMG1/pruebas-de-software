import json
from importlib.resources import files

from playwright.sync_api import sync_playwright


class DemoBrowser:
    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()
        self.page = self.browser.new_page()
        html = files("rag_service").joinpath("web/demo.html").read_text()
        self.page.route(
            "http://demo.local/demo",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=html,
            ),
        )
        self.page.goto("http://demo.local/demo")
        return self.page

    def __exit__(self, *args):
        self.browser.close()
        self.playwright.stop()


def test_wait_state_blocks_duplicate_requests_and_renders_safe_sources():
    with DemoBrowser() as page:
        requests = []
        page.route("**/api/v1/chat/query", lambda route: requests.append(route))
        page.locator("#question").fill("¿Nota mínima?")
        page.locator("#submit").click()
        assert page.locator("#submit").is_disabled() and page.locator("#question").is_disabled()
        page.evaluate("document.getElementById('query-form').requestSubmit()")
        assert len(requests) == 1
        requests[0].fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "answer": "<img src=x onerror=alert(1)> 11 [1]",
                    "insufficient_context": False,
                    "sources": [
                        {
                            "source_id": 1,
                            "title": "<script>bad</script>",
                            "filename": "demo.pdf",
                            "page_start": 1,
                            "page_end": 1,
                            "version": 1,
                            "excerpt": "La nota es 11.",
                        }
                    ],
                }
            ),
        )
        page.locator("#result").wait_for(state="visible")
        assert "<img" in page.locator("#answer").inner_text()
        assert page.locator("#answer img").count() == 0
        assert page.locator("#sources script").count() == 0
        assert "La nota es 11" in page.locator("#sources").inner_text()
        assert page.locator("#submit").is_enabled()


def test_error_recovers_and_insufficient_response_has_no_sources():
    with DemoBrowser() as page:
        page.route(
            "**/api/v1/chat/query",
            lambda route: route.fulfill(
                status=503,
                content_type="application/json",
                body='{"message":"Ollama no disponible."}',
            ),
        )
        page.locator("#question").fill("Pregunta")
        page.locator("#submit").click()
        page.locator("#error").wait_for(state="visible")
        assert page.locator("#submit").is_enabled()
        page.unroute("**/api/v1/chat/query")
        page.route(
            "**/api/v1/chat/query",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "answer": "No hay información suficiente.",
                        "insufficient_context": True,
                        "sources": [],
                    }
                ),
            ),
        )
        page.locator("#submit").click()
        page.locator("#result").wait_for(state="visible")
        assert page.locator("#error").is_hidden() and page.locator("#sources-title").is_hidden()
