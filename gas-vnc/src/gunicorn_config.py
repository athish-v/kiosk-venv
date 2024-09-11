# /dockerstartup/gunicorn_config.py

import multiprocessing

# Bind to port 5000 on all interfaces
bind = "0.0.0.0:5000"

# Reduce the number of workers if needed to avoid overwhelming the system
workers = max(5, multiprocessing.cpu_count())  # Adjust as necessary


# Logging
accesslog = "-"  # Log access logs to stdout
errorlog = "-"   # Log error logs to stdout
loglevel = "info"  # Use debug to capture more detailed logs

# Graceful timeout
timeout = 600  # Longer timeout for VNC startup delay

# Max requests before recycling a worker to prevent memory leaks
max_requests = 100
max_requests_jitter = 20

# Increase the timeout for worker shutdown
graceful_timeout = 60
