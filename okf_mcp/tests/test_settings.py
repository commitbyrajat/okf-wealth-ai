from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from okf_exec.settings import PackageSourceConfig


class PackageSourceConfigTest(unittest.TestCase):
    def test_repository_url_is_derived_from_datapackage_url(self) -> None:
        config = PackageSourceConfig(
            datapackage_url="https://github.com/acme/data/blob/main/datapackage.json"
        )

        self.assertEqual(config.repository_url, "https://github.com/acme/data")

    def test_configured_source_uses_default_alias_when_env_is_missing(self) -> None:
        config = PackageSourceConfig(
            datapackage_url="https://github.com/acme/data/blob/main/datapackage.json",
            env_var="OKF_TEST_SOURCE",
        )

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.configured_source, "github")

    def test_default_source_accepts_alias_descriptor_and_repo_url(self) -> None:
        config = PackageSourceConfig(
            datapackage_url="https://github.com/acme/data/blob/main/datapackage.json"
        )

        self.assertTrue(config.is_default_source(""))
        self.assertTrue(config.is_default_source("github"))
        self.assertTrue(config.is_default_source(config.datapackage_url))
        self.assertTrue(config.is_default_source(config.repository_url))
        self.assertFalse(config.is_default_source("/tmp/datapackage.json"))


if __name__ == "__main__":
    unittest.main()
