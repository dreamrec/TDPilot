"""Small Web Server DAT entry point; keep the router in a cached DAT module.

TD executes the configured callback DAT for each request. Keeping the large
router in its own module avoids reparsing it on the realtime thread for every
HTTP request. All authentication and request policies remain in that router.
"""


def onHTTPRequest(webServerDAT, request, response):
    runtime = webServerDAT.parent().op("callbacks")
    if runtime is None:
        response["statusCode"] = 503
        response["statusReason"] = "Service Unavailable"
        response["content-type"] = "application/json"
        response["data"] = b'{"error":"TDPilot callback runtime is missing"}'
        return response
    return runtime.module.onHTTPRequest(webServerDAT, request, response)
