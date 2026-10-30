import json


class RequestTooLarge(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(self, app, upload_limit_bytes: int = 22 * 1024 * 1024, default_limit_bytes: int = 1024 * 1024):
        self.app = app
        self.upload_limit_bytes = upload_limit_bytes
        self.default_limit_bytes = default_limit_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        limit = self.upload_limit_bytes if path == "/api/knowledge/documents" else self.default_limit_bytes
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length", b"")
        if content_length.isdigit() and int(content_length) > limit:
            await self._reject(send)
            return
        received = 0
        response_started = False

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if not response_started:
                await self._reject(send)

    @staticmethod
    async def _reject(send):
        body = json.dumps({"detail": "Corpo da requisição excede o limite configurado"}).encode("utf-8")
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(body)).encode("ascii"))]})
        await send({"type": "http.response.body", "body": body})
