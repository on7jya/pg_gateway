"""Hot reload of the accounts registry via file polling."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from pg_gateway.config.loader import load_config
from pg_gateway.config.models import AppConfig

logger = logging.getLogger("pg_gateway.reload")


class ConfigReloader:
    """Poll watched files and swap the validated config on change.

    Fail-safe: an invalid update keeps the previous config and logs the error.
    """

    def __init__(
        self,
        *,
        base_path: Path,
        accounts_path: Path | None,
        apply: Callable[[AppConfig], None],
        interval: float = 2.0,
    ) -> None:
        self.base_path = base_path
        self.accounts_path = accounts_path
        self.apply = apply
        self.interval = interval
        self._mtimes: dict[Path, float] = self._snapshot()

    def _watched(self) -> list[Path]:
        paths = [self.base_path]
        if self.accounts_path is not None:
            paths.append(self.accounts_path)
        return paths

    def _snapshot(self) -> dict[Path, float]:
        return {p: p.stat().st_mtime for p in self._watched() if p.exists()}

    def poll(self) -> bool:
        """Reload if any watched file changed; return True when applied."""
        current = self._snapshot()
        if current == self._mtimes:
            return False
        self._mtimes = current
        try:
            new_config = load_config(self.base_path, accounts_path=self.accounts_path)
        except Exception as exc:  # noqa: BLE001 — fail-safe on any load/validate error
            logger.warning("accounts reload failed, keeping previous config: %s", exc)
            return False
        self.apply(new_config)
        logger.info("accounts reloaded (%d accounts)", len(new_config.accounts))
        return True

    async def run(self) -> None:
        """Poll forever; call poll() every ``interval`` seconds."""
        while True:
            await asyncio.sleep(self.interval)
            try:
                self.poll()
            except Exception as exc:  # noqa: BLE001
                logger.warning("reload poll error: %s", exc)
