import os
import signal
import subprocess
import json
import time
from datetime import datetime
import threading

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gpu_manager.settings")
django.setup()

from gpu_manager.settings import SERVER_USERNAME, SERVER_GPUSTAT_PATH, SERVER_IP_LIST
from task.models import GPUTask
from task.utils import run_task
from gpu_info.models import GPUServer
from gpu_info.utils import GPUInfoUpdater, add_server


if __name__ == '__main__':
    for ip in SERVER_IP_LIST:
        if GPUServer.objects.filter(ip=ip).count() == 0:
            add_server(SERVER_USERNAME, ip)

    gpu_updater = GPUInfoUpdater(SERVER_USERNAME, SERVER_GPUSTAT_PATH)
    while True:
        print('{:s}, Running processes: {:d}'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            threading.active_count() - 1)
        )
        # print('Updating GPU status')
        gpu_updater.update_gpu_info()
        for task in GPUTask.objects.filter(status=0):
            available_server = task.find_available_server()
            if available_server is not None:
                t = threading.Thread(target=run_task, args=(task, available_server))
                t.start()
                time.sleep(5)
