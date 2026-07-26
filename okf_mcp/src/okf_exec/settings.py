from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class PackageSourceConfig:
    datapackage_url: str
    env_var: str = "OKF_DATAPACKAGE_SOURCE"
    customer_id_env_var: str = "OKF_CUSTOMER_ID"
    default_alias: str = "github"

    @property
    def repository_url(self) -> str:
        parsed = urlparse(self.datapackage_url)
        owner, repo, *_ = parsed.path.strip("/").split("/")
        return f"{parsed.scheme}://{parsed.netloc}/{owner}/{repo}"

    @property
    def configured_source(self) -> str:
        return os.environ.get(self.env_var, self.default_alias).strip()

    @property
    def configured_customer_id(self) -> str:
        return os.environ.get(self.customer_id_env_var, "").strip()

    def is_default_source(self, source: str) -> bool:
        return source in {
            "",
            self.default_alias,
            self.datapackage_url,
            self.repository_url,
        }


DEFAULT_PACKAGE_SOURCE = PackageSourceConfig(
    datapackage_url=(
        "https://github.com/commitbyrajat/okf-wealth-base/blob/main/datapackage.json"
    )
)
