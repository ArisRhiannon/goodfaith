from goodfaith.extract import classify


def test_external_invite_detected():
    r = classify("come join discord.gg/abc")
    assert r.invite_urls and r.external_invite


def test_own_server_invite_is_not_external():
    r = classify("our home discord.gg/home", own_invite_codes=("home",))
    assert r.invite_urls and not r.external_invite


def test_safe_host_not_flagged():
    r = classify("clip https://youtube.com/x", safe_hosts=("youtube.com",))
    assert r.unsafe_links == ()


def test_unsafe_link_flagged():
    r = classify("look http://sketchy.tld/x")
    assert r.unsafe_links == ("http://sketchy.tld/x",)


def test_invite_url_is_not_double_counted_as_unsafe():
    r = classify("https://discord.gg/abc")
    assert r.invite_urls and r.unsafe_links == ()
