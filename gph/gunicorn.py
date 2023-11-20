#!/usr/bin/env python3
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'uvicorn.workers.UvicornWorker'
loglevel = 'error'
pidfile = 'gunicorn.pid'
reload = True
