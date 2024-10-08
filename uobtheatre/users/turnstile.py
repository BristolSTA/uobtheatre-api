# See details about Turnstile at https://blog.cloudflare.com/turnstile-private-captcha-alternative/

from typing import Optional

import pydantic
import requests
from django.conf import settings


class SiteVerifyRequest(pydantic.BaseModel):
    """
    A model for the request to the Turnstile API.
    """

    secret: str
    response: str


class SiteVerifyResponse(pydantic.BaseModel):
    """
    A model for the response from the Turnstile API.
    """

    success: bool
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: list[str] = pydantic.Field(alias="error-codes", default_factory=list)
    action: Optional[str] = None
    cdata: Optional[str] = None


request_example = {"secret": "0x5ABAAFAAAn72SdCAP75q6sPP9P6zooFZt", "response": "???"}

success_example = {
    "success": True,
    "challenge_ts": "2022-02-28T15:14:30.096Z",
    "hostname": "example.com",
    "error-codes": [],
    "action": "login",
    "cdata": "session_id-123456789",
}

failure_example = {
    "success": False,
    "hostname": "",
    "error-codes": ["invalid-input-response"],
}


def validate(turnstile_response: str) -> SiteVerifyResponse:
    """
    Validates a Turnstile response with Cloudflare, and returns a SiteVerifyResponse.
    """
    if not settings.TURNSTILE_SECRET:
        model = SiteVerifyResponse(
            success=False,
            hostname=None,
        )
        model.error_codes.append("No secret key defined.")
        return model

    if not turnstile_response:
        model = SiteVerifyResponse(
            success=False,
            hostname=None,
        )
        model.error_codes.append("No Turnstile token provided.")
        return model

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    request = SiteVerifyRequest(
        secret=settings.TURNSTILE_SECRET, response=turnstile_response
    )
    try:
        resp = requests.post(url, data=request.model_dump(), timeout=30)
        if resp.status_code != 200:
            model = SiteVerifyResponse(success=False, hostname=None)
            model.error_codes.extend(
                [
                    f"Failure status code: {resp.status_code}",
                    f"Failure details: {resp.text}",
                ]
            )
            return model

        site_response = SiteVerifyResponse(**resp.json())
        return site_response
    except Exception as error:  # pylint: disable=broad-except
        model = SiteVerifyResponse(success=False, hostname=None)
        model.error_codes.extend(
            ["Failure status code: Unknown", f"Failure details: {error}"]
        )
        return model
