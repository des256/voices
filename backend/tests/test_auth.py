from app.auth import make_token, verify_token


def test_token_roundtrip_expiry_and_tamper_rejection():
    tok = make_token("s3cret", expires_at=2_000)
    assert verify_token("s3cret", tok, now=1_999)
    assert not verify_token("s3cret", tok, now=2_001)
    assert not verify_token("other", tok, now=1_000)
    assert not verify_token("s3cret", tok[:-1] + ("0" if tok[-1] != "0" else "1"), now=1_000)
    assert not verify_token("s3cret", "garbage", now=1_000)
    assert not verify_token("s3cret", "", now=1_000)
