import base64

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that authenticates A2A access using an basic auth."""

    # 写一批basic auth的用户,demo鉴权使用
    users = {
        "admin": "123456",
        "user1": "password1",
        "user2": "password2",
    }


    def __init__(
        self,
        app: Starlette,
        public_paths: list[str] = None,
    ):
        super().__init__(app)
        self.public_paths = set(public_paths or [])

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths
        if path in self.public_paths:
            return await call_next(request)

        # Authenticate the request
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            return self._unauthorized(
                'Missing or malformed Authorization header.', request
            )

        encoded_credentials = auth_header[len("Basic "):]
        try:
            decoded_bytes = base64.b64decode(encoded_credentials)
            decoded_credentials = decoded_bytes.decode("utf-8")
        except Exception as e:
            return self._forbidden(f'Authentication failed: {e}', request)

        if ":" not in decoded_credentials:
            return self._forbidden(f'Authentication failed', request)

        username, password = decoded_credentials.split(":", 1)

        # validate
        expected_password = self.users.get(username)
        if expected_password is None or expected_password != password:
            return self._forbidden(f'Authentication failed', request)

        return await call_next(request)


    def _forbidden(self, reason: str, request: Request):
        accept_header = request.headers.get('accept', '')
        if 'text/event-stream' in accept_header:
            return PlainTextResponse(
                f'error forbidden: {reason}',
                status_code=403,
                media_type='text/event-stream',
            )
        return JSONResponse(
            {'error': 'forbidden', 'reason': reason}, status_code=403
        )

    def _unauthorized(self, reason: str, request: Request):
        accept_header = request.headers.get('accept', '')
        if 'text/event-stream' in accept_header:
            return PlainTextResponse(
                f'error unauthorized: {reason}',
                status_code=401,
                media_type='text/event-stream',
            )
        return JSONResponse(
            {'error': 'unauthorized', 'reason': reason}, status_code=401
        )
