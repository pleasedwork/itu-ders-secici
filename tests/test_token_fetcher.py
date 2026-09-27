from token_fetcher import ContinuousTokenFetcher


def test_normalize_token_extracts_cookie_style_authorization():
    token = (
        "Authorization=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    )

    assert ContinuousTokenFetcher._normalize_token(token) == (
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    )


def test_normalize_token_extracts_jwt_from_semicolon_delimited_cookie():
    token = (
        "session=abc; Authorization=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature; path=/"
    )

    assert ContinuousTokenFetcher._normalize_token(token) == (
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    )


def test_extract_jwt_from_obs_auth_endpoint_response():
    class FakeResponse:
        text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
        headers = {}

    assert ContinuousTokenFetcher._extract_jwt_from_response(FakeResponse()) == (
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    )
