"""Shared Flask extension instances.

The Limiter is created here (unbound) and bound to the app in create_app via
init_app, following the application-factory pattern.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Rate limiter, keyed by client IP address.
#
# storage_uri="memory://" keeps the counters in-process. That is appropriate
# for a single-process dev/demo deployment; a multi-process or multi-host
# deployment would point this at Redis/Memcached instead.
#
# No default_limits are configured, so every endpoint is UNLIMITED unless it is
# explicitly decorated with @limiter.limit(...). We only decorate POST /submit,
# so /appeal, /log and /health are intentionally left unthrottled.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
