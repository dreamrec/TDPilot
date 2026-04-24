from td_mcp.events.uri import chop_uri, decode_td_path, encode_td_path, par_uri


def test_encode_decode_td_path_roundtrip():
    path = "/project1/comp.with.dot/noise 1"
    assert decode_td_path(encode_td_path(path)) == path


def test_chop_uri_uses_encoded_path():
    uri = chop_uri("/project1/audio1", "chan1")
    assert uri == "td://chop/path/%2Fproject1%2Faudio1/channel/chan1"


def test_par_uri_uses_encoded_path():
    uri = par_uri("/project1/noise1", "amp")
    assert uri == "td://par/path/%2Fproject1%2Fnoise1/name/amp"
