"""Tests for the self_updater module — GitHub-driven version check + install.

The module's job is to close the multi-layer staleness problem documented
in CLAUDE.md: ``tdpilot.tox`` lives in three places that go out of sync
silently, and the Claude Code plugin cache + the user-data ``~/.tdpilot/``
both lag the latest release until manually reinstalled.

Network calls are injected via a ``fetch_releases`` callable so tests
exercise every branch without touching the network. The production code
defaults to calling the GitHub API via stdlib urllib.
"""

from __future__ import annotations

import urllib.error

import pytest

from td_mcp import self_updater

# ──────────────────────────────────────────────────────────
# Pure version-comparison logic
# ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "older,newer",
    [
        ("1.0.0", "1.0.1"),
        ("1.0.9", "1.1.0"),
        ("1.6.15", "1.6.16"),
        ("1.6.99", "1.7.0"),
        ("1.9.0", "2.0.0"),
        # Tag prefix tolerance — v1.0.0 == 1.0.0 from the comparison standpoint.
        ("v1.0.0", "v1.0.1"),
    ],
)
def test_is_newer_recognizes_higher_version(older, newer):
    assert self_updater.is_newer(latest=newer, installed=older) is True


@pytest.mark.parametrize("a", ["1.0.0", "1.6.15", "2.3.4"])
def test_is_newer_equal_returns_false(a):
    assert self_updater.is_newer(latest=a, installed=a) is False


def test_is_newer_lower_returns_false():
    assert self_updater.is_newer(latest="1.6.14", installed="1.6.15") is False


def test_is_newer_malformed_returns_false_does_not_raise():
    """When either version is unparseable, the safe default is "no update"."""
    assert self_updater.is_newer(latest="not-a-version", installed="1.0.0") is False
    assert self_updater.is_newer(latest="1.0.0", installed="not-a-version") is False


def test_is_newer_strips_v_prefix():
    assert self_updater.is_newer(latest="v1.6.16", installed="1.6.15") is True
    assert self_updater.is_newer(latest="1.6.16", installed="v1.6.15") is True


# ──────────────────────────────────────────────────────────
# run(check_only=True) — happy paths
# ──────────────────────────────────────────────────────────


def _fake_release(tag: str, assets: list[dict] | None = None) -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/dreamrec/TDPilot/releases/tag/{tag}",
        "assets": assets or [],
    }


def test_check_only_reports_up_to_date_when_latest_equals_installed():
    fake = lambda: _fake_release("v1.6.15")  # noqa: E731
    result = self_updater.run(
        check_only=True,
        installed_version="1.6.15",
        fetch_releases=fake,
    )
    assert result["newer_available"] is False
    assert result["installed"] == "1.6.15"
    assert result["latest"] == "1.6.15"
    assert "release_url" in result


def test_check_only_reports_newer_available():
    fake = lambda: _fake_release("v1.6.16")  # noqa: E731
    result = self_updater.run(
        check_only=True,
        installed_version="1.6.15",
        fetch_releases=fake,
    )
    assert result["newer_available"] is True
    assert result["installed"] == "1.6.15"
    assert result["latest"] == "1.6.16"
    assert result["release_url"].endswith("/v1.6.16")


def test_check_only_does_not_touch_disk(tmp_path):
    """check_only=True must never write to disk."""
    fake = lambda: _fake_release("v1.6.16")  # noqa: E731
    result = self_updater.run(
        check_only=True,
        installed_version="1.6.15",
        fetch_releases=fake,
        install_paths=[tmp_path / "site_a", tmp_path / "site_b"],
    )
    assert result["newer_available"] is True
    # No files created.
    assert not any(tmp_path.iterdir())


# ──────────────────────────────────────────────────────────
# run(check_only=True) — error paths
# ──────────────────────────────────────────────────────────


def test_network_failure_returns_structured_error():
    def boom():
        raise RuntimeError("no connection")

    result = self_updater.run(
        check_only=True,
        installed_version="1.6.15",
        fetch_releases=boom,
    )
    assert "error" in result
    assert "no connection" in result["error"]
    # On error, we still report what we know about the installed side.
    assert result["installed"] == "1.6.15"


def test_github_rate_limit_returns_actionable_structured_diagnostics():
    def rate_limited():
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/dreamrec/TDPilot/releases/latest",
            code=403,
            msg="API rate limit exceeded",
            hdrs={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1782345600"},
            fp=None,
        )

    result = self_updater.run(
        check_only=True,
        installed_version="2.0.2",
        fetch_releases=rate_limited,
    )

    assert result["ok"] is False
    assert result["error_code"] == "github_rate_limited"
    assert result["diagnostic"]["http_status"] == 403
    assert result["diagnostic"]["rate_limit_remaining"] == "0"
    assert result["diagnostic"]["rate_limit_reset"] == "1782345600"
    assert any("GH_TOKEN" in item for item in result["diagnostic"]["remediation"])
    assert "secret" not in " ".join(result["diagnostic"]["remediation"]).lower()
    assert result["installed"] == "2.0.2"


def test_empty_release_list_handled():
    """If the GitHub API returns a malformed/empty payload, surface it cleanly."""
    fake = lambda: {}  # noqa: E731
    result = self_updater.run(
        check_only=True,
        installed_version="1.6.15",
        fetch_releases=fake,
    )
    assert "error" in result


# ──────────────────────────────────────────────────────────
# run(check_only=False) — install path with mocked downloader
# ──────────────────────────────────────────────────────────


def test_install_writes_asset_to_all_install_paths(tmp_path):
    """When check_only=False and a newer release exists, the tox is written
    to every configured install path. md5 sums are reported."""
    asset_payload = b"FAKE_TOX_BYTES_v1.6.16"

    def fake_fetch():
        return _fake_release(
            "v1.6.16",
            assets=[
                {
                    "name": "tdpilot.tox",
                    "browser_download_url": "https://example.invalid/tdpilot.tox",
                }
            ],
        )

    def fake_download(url):
        assert url == "https://example.invalid/tdpilot.tox"
        return asset_payload

    site_a = tmp_path / "site_a" / "td_component" / "tdpilot.tox"
    site_b = tmp_path / "site_b" / "td_component" / "tdpilot.tox"

    result = self_updater.run(
        check_only=False,
        installed_version="1.6.15",
        fetch_releases=fake_fetch,
        download_asset=fake_download,
        install_paths=[site_a, site_b],
        asset_name="tdpilot.tox",
    )

    assert result["newer_available"] is True
    assert result["installed_to"] == [str(site_a), str(site_b)]
    assert site_a.read_bytes() == asset_payload
    assert site_b.read_bytes() == asset_payload
    # md5 fields report identical hashes for sync verification.
    md5_a = result["md5"][str(site_a)]
    md5_b = result["md5"][str(site_b)]
    assert md5_a == md5_b
    assert len(md5_a) == 32


def test_install_skips_when_up_to_date(tmp_path):
    """install path is a no-op when installed == latest."""
    fake = lambda: _fake_release(  # noqa: E731
        "v1.6.15",
        assets=[{"name": "tdpilot.tox", "browser_download_url": "x"}],
    )
    target = tmp_path / "td_component" / "tdpilot.tox"

    result = self_updater.run(
        check_only=False,
        installed_version="1.6.15",
        fetch_releases=fake,
        download_asset=lambda _u: pytest.fail("download must not run"),
        install_paths=[target],
        asset_name="tdpilot.tox",
    )
    assert result["newer_available"] is False
    assert "installed_to" not in result or result.get("installed_to") == []
    assert not target.exists()


def test_install_missing_asset_reports_error(tmp_path):
    """If the named asset isn't in the release, surface a clear error
    instead of crashing on a None URL."""

    fake = lambda: _fake_release("v1.6.16", assets=[])  # noqa: E731

    result = self_updater.run(
        check_only=False,
        installed_version="1.6.15",
        fetch_releases=fake,
        download_asset=lambda _u: pytest.fail("must not run"),
        install_paths=[tmp_path / "td_component" / "tdpilot.tox"],
        asset_name="tdpilot.tox",
    )
    assert "error" in result
    assert "asset" in result["error"].lower()


def test_install_missing_asset_reports_available_assets_and_packaging_gap(tmp_path):
    fake = lambda: _fake_release(  # noqa: E731
        "v2.0.3",
        assets=[
            {"name": "tdpilot.zip", "browser_download_url": "https://example.invalid/zip"},
            {"name": "TDPilot.plugin", "browser_download_url": "https://example.invalid/plugin"},
        ],
    )

    result = self_updater.run(
        check_only=False,
        installed_version="2.0.2",
        fetch_releases=fake,
        download_asset=lambda _u: pytest.fail("must not download when tox asset is absent"),
        install_paths=[tmp_path / "td_component" / "tdpilot.tox"],
        asset_name="tdpilot.tox",
    )

    assert result["ok"] is False
    assert result["error_code"] == "release_asset_missing"
    assert result["diagnostic"]["requested_asset"] == "tdpilot.tox"
    assert result["diagnostic"]["available_assets"] == ["tdpilot.zip", "TDPilot.plugin"]
    assert result["diagnostic"]["release_packaging_incomplete"] is True
    assert any(".tox" in item for item in result["diagnostic"]["remediation"])


def test_install_creates_parent_directories(tmp_path):
    """When the install path's parent doesn't exist, it's created."""
    asset_payload = b"x"
    fake = lambda: _fake_release(  # noqa: E731
        "v1.6.16",
        assets=[{"name": "tdpilot.tox", "browser_download_url": "u"}],
    )

    nested = tmp_path / "deep" / "nested" / "td_component" / "tdpilot.tox"
    assert not nested.parent.exists()

    result = self_updater.run(
        check_only=False,
        installed_version="1.6.15",
        fetch_releases=fake,
        download_asset=lambda _u: asset_payload,
        install_paths=[nested],
        asset_name="tdpilot.tox",
    )
    assert nested.exists()
    assert result["newer_available"] is True
