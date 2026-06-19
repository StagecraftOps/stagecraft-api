"""Shared rate limiter.

Defined in its own module so both ``app.main`` and individual routes can import
the same ``Limiter`` instance without a circular import.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
