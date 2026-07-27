from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from frictionless.resources import TextResource

DEFAULT_INSTRUCTIONS_URL = (
    "https://github.com/commitbyrajat/okf-wealth-base/blob/main/knowledge/index.md"
)

logger = logging.getLogger(__name__)

MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


class InstructionReader:
    def __init__(
        self,
        *,
        fetcher: Callable[[str], str] | None = None,
        local_knowledge_root: Path | None = None,
    ) -> None:
        self._fetcher = fetcher or self._read_with_frictionless
        self._local_knowledge_root = local_knowledge_root or find_local_knowledge_root()

    def read(
        self,
        url: str = DEFAULT_INSTRUCTIONS_URL,
        *,
        include_linked: bool = False,
        max_depth: int = 1,
    ) -> dict[str, object]:
        if max_depth < 0:
            raise ValueError("max_depth must be greater than or equal to 0")

        depth = max_depth if include_linked else 0
        return self._read_document(url, depth=depth, visited=set())

    def _read_document(
        self,
        url: str,
        *,
        depth: int,
        visited: set[str],
    ) -> dict[str, object]:
        resolved_url = normalize_markdown_url(url)
        logger.info("fetching instruction document resolved_url=%s", resolved_url)
        if resolved_url in visited:
            logger.info(
                "skipping already-read instruction document url=%s", resolved_url
            )
            return {
                "url": url,
                "resolved_url": resolved_url,
                "content": "",
                "links": [],
                "linked_documents": [],
                "skipped": "already_read",
            }

        visited.add(resolved_url)
        content = self._fetch_text(resolved_url)
        links = extract_markdown_links(content, resolved_url)
        logger.info(
            "fetched instruction document resolved_url=%s link_count=%s",
            resolved_url,
            len(links),
        )
        document: dict[str, object] = {
            "url": url,
            "resolved_url": resolved_url,
            "content": content,
            "links": links,
        }

        if depth <= 0:
            return document

        linked_documents: list[dict[str, object]] = []
        for link in links:
            linked_url = str(link["resolved_url"])
            try:
                linked_documents.append(
                    self._read_document(linked_url, depth=depth - 1, visited=visited)
                )
            except RuntimeError as exception:
                linked_documents.append(
                    {
                        "url": linked_url,
                        "resolved_url": normalize_markdown_url(linked_url),
                        "title": link["title"],
                        "error": str(exception),
                    }
                )
        document["linked_documents"] = linked_documents
        return document

    def _fetch_text(self, url: str) -> str:
        try:
            return self._fetcher(url)
        except ValueError:
            raise
        except Exception as exception:
            fallback = self._read_local_fallback(url)
            if fallback is not None:
                logger.info(
                    "using local instruction fallback url=%s root=%s",
                    url,
                    self._local_knowledge_root,
                )
                return fallback
            raise RuntimeError(
                f'could not read markdown instructions from "{url}": {exception}'
            ) from exception

    def _read_with_frictionless(self, url: str) -> str:
        return TextResource(path=url).read_text()

    def _read_local_fallback(self, url: str) -> str | None:
        local_path = resolve_local_knowledge_path(url, self._local_knowledge_root)
        if local_path is None:
            return None
        return local_path.read_text(encoding="utf-8")


def normalize_markdown_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("instruction url must use http or https")

    if parsed.netloc != "github.com":
        return url

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if len(segments) < 5 or segments[2] != "blob":
        return url

    owner, repository, _, branch, *path_parts = segments
    path = "/".join(path_parts)
    return f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}/{path}"


def extract_markdown_links(markdown_text: str, base_url: str) -> list[dict[str, str]]:
    links = []
    seen_urls: set[str] = set()
    for match in MARKDOWN_LINK_PATTERN.finditer(markdown_text):
        title = match.group(1).strip()
        href = match.group(2).strip()
        if not title or should_skip_link(href):
            continue

        resolved_url = resolve_markdown_link(base_url, href)
        if resolved_url is None or resolved_url in seen_urls:
            continue

        seen_urls.add(resolved_url)
        links.append(
            {
                "title": title,
                "url": href,
                "resolved_url": resolved_url,
            }
        )
    return links


def resolve_markdown_link(base_url: str, href: str) -> str | None:
    clean_href = href.split("#", 1)[0].strip()
    if not clean_href:
        return None

    if clean_href.endswith("/"):
        clean_href = f"{clean_href}index.md"

    if not is_markdown_target(clean_href):
        return None

    base = normalize_markdown_url(base_url)
    if clean_href.startswith("/"):
        raw_root = github_raw_root(base)
        if raw_root is None:
            return urljoin(base, clean_href)
        return f"{raw_root}/{clean_href.lstrip('/')}"

    return normalize_markdown_url(urljoin(base, clean_href))


def should_skip_link(href: str) -> bool:
    lowered = href.lower()
    return lowered.startswith(("#", "mailto:", "tel:", "javascript:"))


def is_markdown_target(href: str) -> bool:
    path = urlparse(href).path
    return path.endswith(".md")


def github_raw_root(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc != "raw.githubusercontent.com":
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 3:
        return None

    owner, repository, branch = segments[:3]
    return f"{parsed.scheme}://{parsed.netloc}/{owner}/{repository}/{branch}"


def find_local_knowledge_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "okf_base" / "knowledge"
        if candidate.is_dir():
            return candidate
    return None


def resolve_local_knowledge_path(url: str, root: Path | None) -> Path | None:
    if root is None:
        return None

    parsed = urlparse(normalize_markdown_url(url))
    if parsed.netloc != "raw.githubusercontent.com":
        return None

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if len(segments) < 5:
        return None

    owner, repository, _branch, directory, *path_parts = segments
    if (
        owner != "commitbyrajat"
        or repository != "okf-wealth-base"
        or directory != "knowledge"
        or not path_parts
    ):
        return None

    candidate = (root / Path(*path_parts)).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        return None
    if not candidate.is_file():
        return None
    return candidate
