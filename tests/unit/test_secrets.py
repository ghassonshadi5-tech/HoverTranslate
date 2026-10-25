from __future__ import annotations

from pathlib import Path

import pytest

from hovertranslate.config.secrets import SecretStore


@pytest.mark.skipif(
    True,
    reason="DPAPI test requires manual enablement on a real Windows user profile.",
)
def test_secret_roundtrip(tmp_path: Path) -> None:
    store = SecretStore(base_dir=tmp_path)

    store.set_secret("provider_key", "super-secret-value")
    assert store.get_secret("provider_key") == "super-secret-value"

    store.delete_secret("provider_key")
    assert store.get_secret("provider_key") is None