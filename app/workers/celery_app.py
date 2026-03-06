from celery import Celery 
from app.core.config import settings # import settings to get Redis URL for Celery configuration

# Initialize Celery app with Redis as both broker and backend, and include tasks from app.workers.tasks

# celery is added for background processing of conversion tasks, 
# allowing the API to respond quickly while heavy work is done asynchronously 
# (asynchronous means it can run in the background without blocking the main thread of execution)
celery = Celery(
    "cad_converter",
    broker=settings.REDIS_URL, 
    # broker is the message queue that Celery uses to receive tasks, using Redis URL from settings
    
    backend=settings.REDIS_URL, 
    # backend is where Celery stores task results, also using Redis URL from settings
    
    include=["app.workers.tasks"], 
    # include the tasks module so Celery knows where to find the task definitions
)

# Enable tracking of task start time for better progress reporting and monitoring
celery.conf.task_track_started = True