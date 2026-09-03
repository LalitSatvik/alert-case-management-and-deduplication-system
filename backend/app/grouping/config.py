"""YAML loader and canonical hash for the grouping-engine configuration.

:func:`load_config` reads the config file at the given (cwd-relative or absolute)
path and returns a fully frozen :class:`~app.grouping.GroupingConfig`.
:func:`config_hash` produces a deterministic sha256 of the config's values so an
engine run can be tied to the exact configuration that produced it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from app.config import get_settings
from app.grouping import FeatureWeights, GroupingConfig, Rule

__all__ = ["config_hash", "get_grouping_config", "load_config"]

# ``app/grouping/config.py`` -> parents[2] == ``backend/`` (the package root).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str) -> GroupingConfig:
    """Parse the grouping config YAML at ``path`` into a :class:`GroupingConfig`.

    ``path`` is resolved as given -- a relative path is relative to the current
    working directory (the tests run from ``backend/`` and pass
    ``"config/grouping.yaml"``); an absolute path also works.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    weights = FeatureWeights(**raw["weights"])
    rules = tuple(
        Rule(
            id=str(entry["id"]),
            enabled=bool(entry["enabled"]),
            blocking_keys=tuple(str(k) for k in entry["blocking_keys"]),
            time_window_seconds=int(entry["time_window_seconds"]),
            amount_tolerance=float(entry["amount_tolerance"]),
            match_keys=tuple(str(k) for k in entry["match_keys"]),
            weight=float(entry["weight"]),
        )
        for entry in raw["rules"]
    )
    return GroupingConfig(
        rules=rules,
        weights=weights,
        similarity_threshold=float(raw["similarity_threshold"]),
        candidate_cap=int(raw["candidate_cap"]),
        time_tau_seconds=int(raw["time_tau_seconds"]),
        dispositions=tuple(str(d) for d in raw["dispositions"]),
        risk_aggregation=raw["risk_aggregation"],
    )


def config_hash(cfg: GroupingConfig) -> str:
    """Return the sha256 hexdigest (64 chars) of ``cfg``'s canonical JSON form.

    Pure function of the config values: ``dataclasses.asdict`` flattens the
    nested frozen dataclasses, ``json.dumps(sort_keys=True, separators=(",",":"))``
    canonicalises it, so the digest is stable across processes and runs.
    """
    canonical = json.dumps(dataclasses.asdict(cfg), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache
def get_grouping_config() -> GroupingConfig:
    """Return the process-wide :class:`GroupingConfig` from ``settings.grouping_config_path``.

    A relative ``grouping_config_path`` is resolved against the ``backend/`` package
    root (not the current working directory) so the engine loads the same config
    whether it is driven from ``backend/``, a test runner, or a deployed process.
    Cached: the config file is read once per process.
    """
    configured = Path(get_settings().grouping_config_path)
    path = configured if configured.is_absolute() else _BACKEND_ROOT / configured
    return load_config(str(path))
