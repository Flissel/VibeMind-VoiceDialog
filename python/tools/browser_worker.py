"""
VibeMind Browser Worker

Playwright-based browser automation for searching images, fetching content,
and other web operations requested by the AI voice assistant.

Designed to be called from client tools when user asks things like:
- "Find images for my cookbook cover"
- "Search for pictures of mountains"
- "Get some reference images for my project"
"""

import asyncio
import os
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed - browser automation unavailable")


@dataclass
class ImageResult:
    """Represents a found image."""
    url: str
    title: str
    source_url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class BrowserWorker:
    """
    Handles browser automation tasks like image search.

    Usage:
        worker = BrowserWorker()
        await worker.start()
        results = await worker.search_images("cookbook cover")
        await worker.close()
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None
        self._started = False

    async def start(self):
        """Initialize browser."""
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        if self._started:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self._started = True
        logger.info("Browser worker started")

    async def close(self):
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self._started = False
        logger.info("Browser worker closed")

    async def search_images(
        self,
        query: str,
        count: int = 5,
        safe_search: bool = True
    ) -> List[ImageResult]:
        """
        Search for images using DuckDuckGo (privacy-friendly, no API key needed).

        Args:
            query: Search terms
            count: Number of images to return
            safe_search: Enable safe search filtering

        Returns:
            List of ImageResult objects
        """
        if not self._started:
            await self.start()

        results = []
        page = await self.browser.new_page()

        try:
            # Use DuckDuckGo Images (no API key needed)
            safe_param = "1" if safe_search else "-1"
            search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&t=h_&iax=images&ia=images&kp={safe_param}"

            await page.goto(search_url, timeout=30000)

            # Wait for images to load
            await page.wait_for_selector(".tile--img__img", timeout=10000)
            await asyncio.sleep(1)  # Let more images load

            # Extract image data
            images = await page.query_selector_all(".tile--img__img")

            for img in images[:count]:
                try:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src")
                    title = await img.get_attribute("alt") or query

                    if src and src.startswith("http"):
                        results.append(ImageResult(
                            url=src,
                            title=title,
                            source_url=search_url,
                            thumbnail_url=src
                        ))
                except Exception as e:
                    logger.warning(f"Failed to extract image: {e}")
                    continue

        except Exception as e:
            logger.error(f"Image search failed: {e}")
        finally:
            await page.close()

        logger.info(f"Found {len(results)} images for '{query}'")
        return results

    async def search_images_unsplash(
        self,
        query: str,
        count: int = 5
    ) -> List[ImageResult]:
        """
        Search for free-to-use images on Unsplash.

        Args:
            query: Search terms
            count: Number of images to return

        Returns:
            List of ImageResult objects (all free to use)
        """
        if not self._started:
            await self.start()

        results = []
        page = await self.browser.new_page()

        try:
            search_url = f"https://unsplash.com/s/photos/{query.replace(' ', '-')}"
            await page.goto(search_url, timeout=30000)

            # Wait for images
            await page.wait_for_selector("figure img", timeout=10000)
            await asyncio.sleep(2)  # Let images load

            # Get image elements
            figures = await page.query_selector_all("figure")

            for figure in figures[:count]:
                try:
                    img = await figure.query_selector("img")
                    if not img:
                        continue

                    src = await img.get_attribute("src")
                    srcset = await img.get_attribute("srcset")
                    alt = await img.get_attribute("alt") or query

                    # Get the best quality URL from srcset
                    if srcset:
                        urls = srcset.split(",")
                        if urls:
                            best = urls[-1].strip().split(" ")[0]
                            src = best

                    if src and src.startswith("http"):
                        results.append(ImageResult(
                            url=src,
                            title=alt,
                            source_url=search_url,
                            thumbnail_url=src
                        ))
                except Exception as e:
                    logger.warning(f"Failed to extract Unsplash image: {e}")

        except Exception as e:
            logger.error(f"Unsplash search failed: {e}")
        finally:
            await page.close()

        logger.info(f"Found {len(results)} Unsplash images for '{query}'")
        return results

    async def download_image(
        self,
        url: str,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Download an image to local storage.

        Args:
            url: Image URL to download
            save_path: Optional path to save to

        Returns:
            Local file path, or None if failed
        """
        if not self._started:
            await self.start()

        page = await self.browser.new_page()

        try:
            # Navigate to image
            response = await page.goto(url, timeout=30000)

            if response and response.ok:
                content = await response.body()

                # Generate path if not provided
                if not save_path:
                    ext = url.split(".")[-1].split("?")[0][:4]
                    if ext not in ["jpg", "jpeg", "png", "gif", "webp"]:
                        ext = "jpg"
                    save_dir = Path(__file__).parent.parent / "downloads"
                    save_dir.mkdir(exist_ok=True)
                    save_path = str(save_dir / f"image_{hash(url) % 10000:04d}.{ext}")

                with open(save_path, "wb") as f:
                    f.write(content)

                logger.info(f"Downloaded image to {save_path}")
                return save_path

        except Exception as e:
            logger.error(f"Failed to download image: {e}")
        finally:
            await page.close()

        return None

    async def get_page_content(self, url: str) -> Optional[str]:
        """
        Get text content from a webpage.

        Args:
            url: Page URL

        Returns:
            Page text content
        """
        if not self._started:
            await self.start()

        page = await self.browser.new_page()

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("domcontentloaded")

            # Get main content text
            content = await page.inner_text("body")
            return content[:10000]  # Limit length

        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return None
        finally:
            await page.close()


# =============================================================================
# TOOL FUNCTIONS
# =============================================================================

# Global worker instance
_worker: Optional[BrowserWorker] = None


async def _get_worker() -> BrowserWorker:
    """Get or create the browser worker."""
    global _worker
    if _worker is None:
        _worker = BrowserWorker(headless=True)
        await _worker.start()
    return _worker


def search_images_tool(params: Dict[str, Any]) -> str:
    """
    Search for images on the web.

    Called when user says things like:
    - "Find images for my cookbook cover"
    - "Search for pictures of sunsets"
    - "Get some reference images for mountains"

    Args (via params):
        query: Search terms (required)
        count: Number of images to find (default: 5)
        source: "duckduckgo" or "unsplash" (default: "unsplash")

    Returns:
        Description of found images
    """
    query = params.get("query", "").strip()
    count = int(params.get("count", 5))
    source = params.get("source", "unsplash")

    if not query:
        return "What should I search for? Please describe the images you want."

    if not HAS_PLAYWRIGHT:
        return "Browser automation is not available. Install Playwright with: pip install playwright && playwright install chromium"

    # Run async search
    async def do_search():
        worker = await _get_worker()
        if source == "unsplash":
            return await worker.search_images_unsplash(query, count)
        else:
            return await worker.search_images(query, count)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context
            future = asyncio.ensure_future(do_search())
            results = asyncio.get_event_loop().run_until_complete(future)
        else:
            results = loop.run_until_complete(do_search())
    except RuntimeError:
        # No event loop, create one
        results = asyncio.run(do_search())

    if not results:
        return f"I couldn't find any images for '{query}'. Try different search terms."

    # Format results for voice
    parts = [f"I found {len(results)} images for '{query}':"]
    for i, img in enumerate(results, 1):
        parts.append(f"{i}. {img.title}")

    return " ".join(parts)


def download_image_tool(params: Dict[str, Any]) -> str:
    """
    Download an image from URL.

    Called when user confirms they want to save an image.

    Args (via params):
        url: Image URL to download (required)

    Returns:
        Confirmation with file path
    """
    url = params.get("url", "").strip()

    if not url:
        return "Which image URL should I download?"

    if not HAS_PLAYWRIGHT:
        return "Browser automation is not available."

    async def do_download():
        worker = await _get_worker()
        return await worker.download_image(url)

    try:
        path = asyncio.run(do_download())
    except Exception as e:
        return f"Failed to download image: {e}"

    if path:
        return f"Downloaded image to {path}"
    else:
        return "Failed to download the image."


# Tool registry
BROWSER_TOOLS = {
    "search_images": search_images_tool,
    "download_image": download_image_tool,
}


def register_browser_tools(tools_manager) -> None:
    """
    Register browser tools with the ClientToolsManager (with observer logging).

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering browser tools with observer...")
    for tool_name, tool_func in BROWSER_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    "BrowserWorker",
    "ImageResult",
    "search_images_tool",
    "download_image_tool",
    "BROWSER_TOOLS",
    "register_browser_tools",
    "HAS_PLAYWRIGHT",
]
