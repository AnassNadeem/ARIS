"""Runtime compatibility shims for ARIS dependencies.

`requests 2.34.2` annotates `requests.models.Response` with forward-ref
strings (`RequestsCookieJar`, `HTTPAdapter`) that are NOT imported into
`requests.models` itself. When `requests-cache` serialises a response via
`attrs.resolve_types -> typing.get_type_hints`, evaluation of those strings
crashes with `NameError`, which fastf1 then reports as
"Failed to load any schedule data."

Injecting the missing names into the module namespace makes the forward
refs resolvable. No requests/requests-cache/cattrs behaviour changes.
"""

from __future__ import annotations


def apply() -> None:
    import requests.adapters
    import requests.models
    from requests.cookies import RequestsCookieJar

    if not hasattr(requests.models, "RequestsCookieJar"):
        requests.models.RequestsCookieJar = RequestsCookieJar
    if not hasattr(requests.models, "HTTPAdapter"):
        requests.models.HTTPAdapter = requests.adapters.HTTPAdapter
