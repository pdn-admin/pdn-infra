# Gunicorn configuration for PDN Chat

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes - single worker with gevent for concurrent I/O
# Keeps all in-memory state consistent (conversation_history, admin_sessions, token_usage)
# while handling 50+ concurrent LLM calls without blocking
workers = 1
worker_class = "gevent"
worker_connections = 100
timeout = 180  # 3 minutes for LLM calls (Sonnet averages 10-15s, max with retries ~60s)
keepalive = 2

# Restart workers to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "pdn-chat"

# Server mechanics
daemon = False
preload_app = True

# Graceful shutdown
graceful_timeout = 30
