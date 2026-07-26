from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .agent import AgentRunTimeoutError, run_question
from .config import AgentSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="okf-agent",
        description="Ask the OKF Pydantic AI agent a wealth-management question.",
    )
    parser.add_argument("question", help="Question to answer using OKF instructions.")
    parser.add_argument(
        "--session-id",
        default="default",
        help="Stable memory namespace for this user or conversation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full typed OkfAgentAnswer as JSON.",
    )
    return parser


async def run_async(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        answer = await run_question(
            args.question,
            session_id=args.session_id,
            settings=AgentSettings(),
        )
    except AgentRunTimeoutError as exception:
        print(str(exception), file=sys.stderr)
        return 124

    if args.json:
        print(json.dumps(answer.model_dump(), indent=2))
    else:
        print(answer.answer)
        print()
        print("Instruction URLs:")
        for url in answer.instruction_urls:
            print(f"- {url}")
        if answer.data_sources:
            print()
            print("Data sources:")
            for source in answer.data_sources:
                print(f"- {source.name} ({source.source_type})")

    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(run_async(argv)))
