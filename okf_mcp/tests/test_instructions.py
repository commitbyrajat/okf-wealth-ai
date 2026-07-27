from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from okf_exec.instructions import (
    DEFAULT_INSTRUCTIONS_URL,
    InstructionReader,
    extract_markdown_links,
    normalize_markdown_url,
    resolve_markdown_link,
)


class InstructionsTest(unittest.TestCase):
    def test_normalizes_github_blob_url_to_raw_url(self) -> None:
        self.assertEqual(
            normalize_markdown_url(DEFAULT_INSTRUCTIONS_URL),
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/index.md"
            ),
        )

    def test_resolves_relative_and_bundle_root_markdown_links(self) -> None:
        base_url = normalize_markdown_url(DEFAULT_INSTRUCTIONS_URL)

        self.assertEqual(
            resolve_markdown_link(base_url, "portfolio.md"),
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/portfolio.md"
            ),
        )
        self.assertEqual(
            resolve_markdown_link(base_url, "/knowledge/funds.md"),
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/funds.md"
            ),
        )

    def test_extracts_only_markdown_instruction_links(self) -> None:
        links = extract_markdown_links(
            "\n".join(
                [
                    "[Funds](funds.md)",
                    "[Funds again](funds.md)",
                    "![Diagram](diagram.md)",
                    "[External](https://example.com/readme.md)",
                    "[Anchor](#routing)",
                    "[Website](https://example.com)",
                ]
            ),
            normalize_markdown_url(DEFAULT_INSTRUCTIONS_URL),
        )

        self.assertEqual(
            [link["title"] for link in links],
            ["Funds", "External"],
        )

    def test_reader_can_include_linked_documents(self) -> None:
        documents = {
            normalize_markdown_url(DEFAULT_INSTRUCTIONS_URL): (
                "# Knowledge Index\n\n"
                "* [Funds](funds.md) - fund concepts\n"
                "* [Transactions](/knowledge/transactions.md)\n"
            ),
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/funds.md"
            ): "# Funds\n\nUse this for fund details.\n",
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/transactions.md"
            ): "# Transactions\n\nUse this for transaction records.\n",
        }

        reader = InstructionReader(fetcher=documents.__getitem__)
        result = reader.read(include_linked=True)

        self.assertEqual(
            result["resolved_url"], normalize_markdown_url(DEFAULT_INSTRUCTIONS_URL)
        )
        self.assertEqual(len(result["links"]), 2)
        self.assertEqual(len(result["linked_documents"]), 2)
        self.assertIn("fund details", result["linked_documents"][0]["content"])

    def test_reader_rejects_non_http_urls(self) -> None:
        reader = InstructionReader(fetcher=lambda _: "")

        with self.assertRaises(ValueError):
            reader.read("file:///tmp/index.md")

    def test_reader_falls_back_to_local_knowledge_for_github_urls(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.md").write_text("# Local Index\n", encoding="utf-8")

            reader = InstructionReader(
                fetcher=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
                local_knowledge_root=root,
            )
            result = reader.read(DEFAULT_INSTRUCTIONS_URL)

        self.assertEqual(result["content"], "# Local Index\n")
        self.assertEqual(
            result["resolved_url"],
            "https://raw.githubusercontent.com/commitbyrajat/"
            "okf-wealth-base/main/knowledge/index.md",
        )


if __name__ == "__main__":
    unittest.main()
