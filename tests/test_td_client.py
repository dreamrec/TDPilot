"""Tests for TDClient construction and URL handling."""

from td_mcp.td_client import TDClient


class TestTDClientBaseURL:
    """Verify base_url construction with various host/scheme combinations."""

    def test_default_localhost(self):
        c = TDClient()
        assert c.base_url == "http://127.0.0.1:9981"

    def test_custom_host_and_port(self):
        c = TDClient(host="10.0.0.5", port=8080)
        assert c.base_url == "http://10.0.0.5:8080"

    def test_hostname_works(self):
        c = TDClient(host="desktop-3lurf0p.tail88651a.ts.net", port=9981)
        assert c.base_url == "http://desktop-3lurf0p.tail88651a.ts.net:9981"

    def test_https_via_scheme_param(self):
        c = TDClient(host="desktop-3lurf0p.tail88651a.ts.net", port=9981, scheme="https")
        assert c.base_url == "https://desktop-3lurf0p.tail88651a.ts.net:9981"

    def test_scheme_extracted_from_host(self):
        """If someone passes a full URL as host, extract the scheme automatically."""
        c = TDClient(host="https://desktop-3lurf0p.tail88651a.ts.net", port=9981)
        assert c.base_url == "https://desktop-3lurf0p.tail88651a.ts.net:9981"

    def test_trailing_slash_stripped(self):
        c = TDClient(host="myhost.local/", port=9981)
        assert c.base_url == "http://myhost.local:9981"

    def test_full_url_with_trailing_slash(self):
        c = TDClient(host="https://myhost.local/", port=443)
        assert c.base_url == "https://myhost.local:443"
