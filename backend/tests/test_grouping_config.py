from app.grouping import ENGINE_VERSION
from app.grouping.config import config_hash, load_config


def test_engine_version_is_pinned():
    assert ENGINE_VERSION == "1.0.0"


def test_load_config_parses_rules_and_weights(tmp_path):
    cfg = load_config("config/grouping.yaml")
    assert cfg.similarity_threshold == 0.72
    assert cfg.candidate_cap == 500
    assert any(r.id == "same-txn-dispute" for r in cfg.rules)
    assert abs(sum(vars(cfg.weights).values()) - 1.0) < 1e-6


def test_config_hash_is_deterministic():
    a = config_hash(load_config("config/grouping.yaml"))
    b = config_hash(load_config("config/grouping.yaml"))
    assert a == b and len(a) == 64
