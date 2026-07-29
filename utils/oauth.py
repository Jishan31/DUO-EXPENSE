"""
Google and Apple OAuth sign-in.

Google: standard OAuth2/OIDC, testable on localhost.
Apple: "Sign In with Apple" requires an Apple Developer account ($99/year),
and Apple does NOT allow http:// or localhost redirect URIs at all — it can
only be tested once the app is deployed on a real HTTPS domain. The "client
secret" isn't a static string; Apple requires a short-lived JWT signed with
your private key, regenerated here on each request rather than stored.
"""
import os
import time
import jwt
from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def google_configured():
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def apple_configured():
    return bool(
        os.environ.get("APPLE_CLIENT_ID") and os.environ.get("APPLE_TEAM_ID")
        and os.environ.get("APPLE_KEY_ID") and os.environ.get("APPLE_PRIVATE_KEY")
    )


def init_oauth(app):
    oauth.init_app(app)

    if google_configured():
        oauth.register(
            name="google",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    if apple_configured():
        oauth.register(
            name="apple",
            client_id=os.environ["APPLE_CLIENT_ID"],
            client_secret=_build_apple_client_secret(),
            server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
            client_kwargs={"scope": "name email", "response_mode": "form_post"},
        )


def _build_apple_client_secret():
    """
    Apple's client secret is a JWT, not a fixed string — it must be signed with
    the private key from your .p8 file and expires after at most 6 months.
    Generated fresh at startup rather than stored anywhere.
    """
    private_key = os.environ["APPLE_PRIVATE_KEY"].replace("\\n", "\n")
    now = int(time.time())
    payload = {
        "iss": os.environ["APPLE_TEAM_ID"],
        "iat": now,
        "exp": now + 60 * 60 * 24 * 30,  # 30 days — safely under Apple's 6-month cap
        "aud": "https://appleid.apple.com",
        "sub": os.environ["APPLE_CLIENT_ID"],
    }
    headers = {"kid": os.environ["APPLE_KEY_ID"]}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
