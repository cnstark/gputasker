import os
import signal
import subprocess
import json
import time
import traceback
import logging

from gpu_tasker.settings import RUNNING_LOG_DIR
from .models import GPUTask, GPUTaskRunningLog

from notification.email_notification import \
    send_task_start_email, send_task_finish_email, send_task_fail_email


task_logger = logging.getLogger('django.task')


def generate_ssh_cmd(host, user, exec_cmd, port=22, private_key_path=None):
    exec_cmd = exec_cmd.replace('$', '\\$')
    if private_key_path is None:
        cmd = "ssh -o StrictHostKeyChecking=no -p {:d} {}@{} \"{}\"".format(port, user, host, exec_cmd)
    else:
        cmd = "ssh -o StrictHostKeyChecking=no -p {:d} -i {} {}@{} \"{}\"".format(port, private_key_path, user, host, exec_cmd)
    return cmd


class RemoteProcess:
    def __init__(self, user, host, cmd, workspace="~", port=22, private_key_path=None, output_file=None):
        self.cmd = generate_ssh_cmd(host, user, "cd {} && {}".format(workspace, cmd), port, private_key_path)
        task_logger.info('cmd:\n' + self.cmd)
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
    def __init__(self, user, host, gpus, cmd, workspace="~", port=22, private_key_path=None, output_file=None):
        env = 'export CUDA_VISIBLE_DEVICES={}'.format(','.join(map(str, gpus)))
        cmd = 'bash -c \'{}\n{}\n\''.format(env, cmd)
        super(RemoteGPUProcess, self).__init__(user, host, cmd, workspace, port, private_key_path, output_file)


def run_task(task, available_server):
    server = available_server['server']
    gpus = available_server['gpus']
    index = task.task_logs.all().count()
    log_file_path = os.path.join(
        RUNNING_LOG_DIR,
        '{:d}_{:s}_{:s}_{:d}_{:d}.log'.format(task.id, task.name, server.ip, index, int(time.time()))
    )
    # create running_log
    running_log = GPUTaskRunningLog(
        index=index,
        task=task,
        server=server,
        pid=-1,
        gpus=','.join(map(str, gpus)),
        log_file_path=log_file_path,
        status=1
    )
    running_log.save()
    try:
        # run process
        process = RemoteGPUProcess(
            task.user.config.server_username,
            server.ip,
            gpus,
            task.cmd,
            task.workspace,
            server.port,
            task.user.config.server_private_key_path,
            log_file_path
        )
        pid = process.pid()
        task_logger.info('Task {:d}-{:s} is running, pid: {:d}'.format(task.id, task.name, pid))

        # save process status
        running_log.pid = pid
        running_log.save()
        server.set_gpus_busy(gpus)
        server.save()
        task.status = 1
        task.save()

        # send email
        send_task_start_email(running_log)

        # wait for return
        return_code = process.get_return_code()
        task_logger.info('Task {:d}-{:s} stopped, return_code: {:d}'.format(task.id, task.name, return_code))

        # save process status
        running_log.status = 2 if return_code == 0 else -1
        running_log.save()
        task.status = 2 if return_code == 0 else -1
        task.save()

        # send email
        if return_code == 0:
            send_task_finish_email(running_log)
        else:
            send_task_fail_email(running_log)
    except Exception:
        es = traceback.format_exc()
        task_logger.error(es)
        running_log.status = -1
        running_log.save()
        task.status = -1
        task.save()
        with open(log_file_path, 'a') as f:
            f.write('\n')
            f.write(es)
    finally:
        server.set_gpus_free(gpus)
        server.save()
