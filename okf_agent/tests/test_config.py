from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from okf_agent.config import AgentSettings, ENV_FILE


class ConfigTest(unittest.TestCase):
    def test_env_file_path_points_to_okf_agent_root(self) -> None:
        self.assertEqual(ENV_FILE.name, ".env")
        self.assertEqual(ENV_FILE.parent.name, "okf_agent")

    def test_settings_can_load_okf_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "OKF_AGENT_MODEL=openai:gpt-5",
                        "OKF_MCP_URL=http://127.0.0.1:9000/mcp/",
                        "OKF_AGENT_MEMORY_MAX_SIZE=7",
                        "OKF_AGENT_LOG_LEVEL=DEBUG",
                        "OKF_AGENT_RUN_TIMEOUT_SECONDS=45",
                        "OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS=10",
                        "OKF_AGENT_MAX_MODEL_REQUESTS=3",
                        "OKF_AGENT_MAX_TOOL_CALLS=5",
                        "OKF_AGENT_MAX_OUTPUT_TOKENS=456",
                    ]
                ),
                encoding="utf-8",
            )

            settings = AgentSettings(_env_file=env_file)

        self.assertEqual(settings.model, "openai:gpt-5")
        self.assertEqual(settings.mcp_url, "http://127.0.0.1:9000/mcp/")
        self.assertEqual(settings.memory_max_size, 7)
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.run_timeout_seconds, 45)
        self.assertEqual(settings.model_request_timeout_seconds, 10)
        self.assertEqual(settings.max_model_requests, 3)
        self.assertEqual(settings.max_tool_calls, 5)
        self.assertEqual(settings.max_output_tokens, 456)

    def test_default_output_token_limit_is_large_enough_for_structured_answers(
        self,
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = AgentSettings(_env_file=None)

        self.assertEqual(settings.max_output_tokens, 4_000)

    def test_env_example_documents_runtime_knobs(self) -> None:
        env_example = ENV_FILE.with_name(".env.example")
        content = env_example.read_text(encoding="utf-8")

        self.assertIn("OKF_AGENT_MAX_OUTPUT_TOKENS=4000", content)
        self.assertIn("OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS=60", content)
        self.assertIn("OPENAI_API_KEY=", content)

    def test_dotenv_does_not_override_exported_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "from-shell"}):
                load_dotenv(env_file, override=False)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "from-shell")


if __name__ == "__main__":
    unittest.main()
