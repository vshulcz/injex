"""Django integration: per-request scope on request.injex, HttpRequest in the
scope context, and scoped resources finalized when the response returns."""

import pytest

pytest.importorskip("django")

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        ALLOWED_HOSTS=["*"],
        DATABASES={},
        INSTALLED_APPS=[],
        INJEX_CONTAINER=None,
    )

import django

django.setup()

from collections.abc import Iterator  # noqa: E402

from django.core.exceptions import ImproperlyConfigured  # noqa: E402
from django.http import HttpRequest, HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from injex import Container  # noqa: E402
from injex.ext.django import InjexMiddleware  # noqa: E402


def _run(container, view, path="/x", **headers):
    settings.INJEX_CONTAINER = container
    middleware = InjexMiddleware(view)
    request = RequestFactory().get(path, **{f"HTTP_{k}": v for k, v in headers.items()})
    return middleware(request)


def test_middleware_resolves_and_injects_the_request():
    class CurrentUser:
        def __init__(self, request: HttpRequest) -> None:
            self.user = request.headers.get("X-User", "anon")

    container = Container()
    container.add_context(HttpRequest)
    container.add_transient(CurrentUser)

    def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse(request.injex.resolve(CurrentUser).user)

    assert _run(container, view, X_USER="ada").content == b"ada"
    assert _run(container, view).content == b"anon"  # per request


def test_scoped_resource_finalized_after_response():
    events: list[str] = []

    class Session: ...

    def open_session() -> Iterator[Session]:
        events.append("open")
        try:
            yield Session()
        finally:
            events.append("close")

    container = Container()
    container.add_scoped_factory(Session, open_session)

    def view(request: HttpRequest) -> HttpResponse:
        request.injex.resolve(Session)
        events.append("view")
        return HttpResponse("ok")

    _run(container, view)
    assert events == ["open", "view", "close"]  # closed when the scope exits


def test_container_string_path_is_supported():
    settings.INJEX_CONTAINER = "tests._cli_app:container"
    middleware = InjexMiddleware(lambda request: HttpResponse("ok"))
    assert middleware.container is not None


def test_missing_container_setting_raises():
    settings.INJEX_CONTAINER = None
    with pytest.raises(ImproperlyConfigured):
        InjexMiddleware(lambda request: HttpResponse("ok"))
