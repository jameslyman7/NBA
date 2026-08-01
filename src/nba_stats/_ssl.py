"""Use the OS certificate store for HTTPS (fixes corporate/AV SSL inspection)."""

from __future__ import annotations

import truststore

truststore.inject_into_ssl()
