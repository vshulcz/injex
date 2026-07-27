"""Django integration for Injex.

Thin glue, not a new container: it opens one Injex scope per request and exposes
it on the request. Point the middleware at your container and resolve from the
scope in views.

    # settings.py -- "module:attr" import path, or a Container instance
    INJEX_CONTAINER = "myapp.bootstrap:build_container"
    MIDDLEWARE = [..., "injex.ext.django.InjexMiddleware"]

    # views.py
    def register(request):
        request.injex.resolve(RegisterUser).execute(...)

The request is placed in the scope's context, so a service registered with
``container.add_context(HttpRequest)`` receives the live request. Install with
``pip install injex[django]``.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse

from injex import Container


def _load_container() -> Container:
    target: Any = getattr(settings, "INJEX_CONTAINER", None)
    if target is None:
        raise ImproperlyConfigured(
            "INJEX_CONTAINER is not set. Point it at your container, e.g. "
            "INJEX_CONTAINER = 'myapp.bootstrap:build_container'."
        )
    if isinstance(target, str):
        module_name, _, attr = target.partition(":")
        if not attr:
            raise ImproperlyConfigured(
                f"INJEX_CONTAINER must be 'module:attribute', got {target!r}."
            )
        target = getattr(importlib.import_module(module_name), attr)
    if callable(target) and not isinstance(target, Container):
        target = target()
    if not isinstance(target, Container):
        raise ImproperlyConfigured(
            "INJEX_CONTAINER did not resolve to a Container "
            f"(got {type(target).__name__})."
        )
    return target


class InjexMiddleware:
    """Opens an Injex scope per request, sets it on ``request.injex``, and closes
    it (finalizing scoped resources) when the response is returned."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.container = _load_container()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        with self.container.create_scope(context={HttpRequest: request}) as scope:
            request.injex = scope
            return self.get_response(request)
