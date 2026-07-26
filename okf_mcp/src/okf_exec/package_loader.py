from __future__ import annotations

from frictionless import Package
from frictionless.exception import FrictionlessException

from .errors import format_frictionless_exception
from .settings import DEFAULT_PACKAGE_SOURCE, PackageSourceConfig
from .validation import PackageValidator


class PackageLoader:
    def __init__(
        self,
        *,
        config: PackageSourceConfig = DEFAULT_PACKAGE_SOURCE,
        validator: PackageValidator | None = None,
    ) -> None:
        self.config = config
        self.validator = validator or PackageValidator()

    def load(self) -> Package:
        source = self.config.configured_source
        try:
            package = (
                self.load_from_github()
                if self.config.is_default_source(source)
                else Package(source)
            )
        except FrictionlessException as exception:
            message = format_frictionless_exception(exception)
            raise RuntimeError(f"Package loading failed:\n{message}") from exception

        self.validator.validate(package)
        return package

    def load_from_github(self) -> Package:
        from frictionless import portals

        return Package(
            self.config.repository_url,
            control=portals.GithubControl(),
        )
