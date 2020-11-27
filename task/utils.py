import os
import signal
import subprocess
import json
import time

from gpu_manager.settings import SERVER_USERNAME
from .models import GPUTask, GPUTaskRunningLog


class RemoteProcess:
    def __init__(self, user, host, cmd, workspace="~", output_file=None):
        self.cmd = "ssh " + user + "@" + host + " \"" + "cd " + workspace + " && " + cmd + "\""
        print(self.cmd)
        if output_file is not None:
            self.output_file = output_file
            with open(self.output_file, "wb") as out:
                self.proc = subprocess.Popen(self.cmd, shell=True, stdout=out, stderr=out, bufsize=1)
        else:
            self.proc = subprocess.Popen(self.cmd, shell=True)

    def pid(self):
        return self.proc.pid

    def kill(self):
        # os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        os.kill(self.proc.pid, signal.SIGKILL)

    def get_return_code(self):
        self.proc.wait()
        return self.proc.returncode


class RemoteGPUProcess(RemoteProcess):
    def __init__(self, user, host, gpus, cmd, workspace="~", output_file=None):
        env = 'CUDA_VISIBLE_DEVICES=' + ','.join(map(str, gpus))
        cmd = env + ' bash -c \'' + cmd + '\''
        super(RemoteGPUProcess, self).__init__(user, host, cmd, workspace, output_file)


def run_task(task, available_server):
    server = available_server['server']
    gpus = available_server['gpus']
    index = task.task_logs.all().count()
    log_file_path = os.path.join(
        'running_log',
        '{:d}_{:s}_{:s}_{:d}_{:d}.log'.format(task.id, task.name, server.ip, index, int(time.time()))
    )
    process = RemoteGPUProcess(SERVER_USERNAME, server.ip, gpus, task.cmd, task.workspace, log_file_path)
    pid = process.pid()
    print('Task {:d}-{:s} is running, pid: {:d}'.format(task.id, task.name, pid))
    server.set_gpus_busy(gpus)
    server.save()
    running_log = GPUTaskRunningLog(
        index=index,
        task=task,
        server=server,
        pid=pid,
        gpus=','.join(map(str, gpus)),
        log_file_path=log_file_path,
        status=1
    )
    running_log.save()
    task.status = 1
    task.save()
    return_code = process.get_return_code()
    print('Task {:d}-{:s} stopped, return_code: {:d}'.format(task.id, task.name, return_code))
    server.set_gpus_free(gpus)
    server.save()
    running_log.status = 2 if return_code == 0 else -1
    running_log.save()
    task.status = 2 if return_code == 0 else -1
    task.save()
