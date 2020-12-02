import os
import signal
import subprocess
import json
import time
from datetime import datetime
import threading

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gpu_tasker.settings")
django.setup()

from base.utils import get_admin_config
from task.models import GPUTask
from task.utils import run_task
from gpu_info.models import GPUServer
from gpu_info.utils import GPUInfoUpdater, add_hostname


if __name__ == '__main__':
    server_username, server_private_key_path, gpustat_path = get_admin_config()

    gpu_updater = GPUInfoUpdater(server_username, gpustat_path, server_private_key_path)
    while True:
        print('{:s}, Running processes: {:d}'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            threading.active_count() - 1)
        )
        start_time = time.time()
        gpu_updater.update_gpu_info()
        for task in GPUTask.objects.filter(status=0):
            available_server = task.find_available_server()
            if available_server is not None:
                t = threading.Thread(target=run_task, args=(task, available_server))
                t.start()
                time.sleep(5)
        end_time = time.time()

        # 确保至少间隔十秒更新一次
        duration = end_time - start_time
        if duration < 10:
            time.sleep(10 - duration)
