# gunicorn.conf.py — production server config
# Run with: gunicorn -c gunicorn.conf.py "app:create_app('config.ProductionConfig')"

import multiprocessing

bind             = "127.0.0.1:5000"
workers          = 1          # DeepFace is heavy — 1 worker + threads is safer
threads          = 4
worker_class     = "gthread"
timeout          = 120        # DeepFace can be slow on first inference
keepalive        = 5
max_requests     = 200
max_requests_jitter = 50

# Logging
accesslog        = "/var/log/faceid/access.log"
errorlog         = "/var/log/faceid/error.log"
loglevel         = "info"

# Preload (loads DeepFace model once, shared across threads)
preload_app      = True
