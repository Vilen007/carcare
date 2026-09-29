from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def rate_limit(prefix, limit=10, period=300):
    """Small single-node rate limiter suitable for form abuse protection."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
            identity = f"user:{request.user.pk}" if request.user.is_authenticated else f"ip:{ip}"
            key = f"rate:{prefix}:{identity}"
            attempts = cache.get(key, 0)
            if attempts >= limit:
                return HttpResponse("Too many attempts. Please try again shortly.", status=429)
            if attempts:
                cache.incr(key)
            else:
                cache.set(key, 1, period)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
