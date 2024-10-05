# See details about Turnstile at https://blog.cloudflare.com/turnstile-private-captcha-alternative/

from typing import Optional
from django.conf import settings

import pydantic
import requests

class SiteVerifyRequest(pydantic.BaseModel):
    secret: str
    response: str


class SiteVerifyResponse(pydantic.BaseModel):
    success: bool
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: list[str] = pydantic.Field(
        alias="error-codes", default_factory=list)
    action: Optional[str] = None
    cdata: Optional[str] = None


request_example = {
    "secret": "0x5ABAAFAAAn72SdCAP75q6sPP9P6zooFZt",
    "response": "???"
}

success_example = {
    "success": True,
    "challenge_ts": "2022-02-28T15:14:30.096Z",
    "hostname": "example.com",
    "error-codes": [],
    "action": "login",
    "cdata": "session_id-123456789"
}

failure_example = {
    "success": False,
    "hostname": "",
    "error-codes": [
        "invalid-input-response"
    ]
}


def validate(turnstile_response: str) -> SiteVerifyResponse:
    if not settings.TURNSTILE_SECRET:
        raise Exception(
            "No secret key is defined.")

    if not turnstile_response:
        model = SiteVerifyResponse(success=False, hostname=None,)
        model.error_codes.append(
            'Submitted with no cloudflare client response')
        return model

    url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    model = SiteVerifyRequest(
        secret=settings.TURNSTILE_SECRET, response=turnstile_response)
    try:
        resp = requests.post(url, data=model.dict())
        if resp.status_code != 200:
            model = SiteVerifyResponse(success=False, hostname=None)
            model.error_codes.extend([
                f'Failure status code: {resp.status_code}',
                f'Failure details: {resp.text}'])
            return model

        site_response = SiteVerifyResponse(**resp.json())
        return site_response
    except Exception as x:
        model = SiteVerifyResponse(success=False, hostname=None)
        model.error_codes.extend([
            f'Failure status code: Unknown',
            f'Failure details: {x}'])
        return model