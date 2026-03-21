"""Constants for the Grooveprint integration."""

DOMAIN = "grooveprint"

CONF_SERVER_URL = "server_url"
CONF_LISTENER_URL = "listener_url"

DEFAULT_SERVER_URL = "http://localhost:8457"
DEFAULT_LISTENER_URL = "http://localhost:8458"

PLATFORMS = ["media_player", "sensor", "switch"]

RECONNECT_INTERVAL = 5  # seconds
LISTENER_POLL_INTERVAL = 5  # seconds
SSE_HEARTBEAT_TIMEOUT = 60  # seconds
