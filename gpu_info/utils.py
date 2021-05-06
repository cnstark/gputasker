import os
import subprocess
import json
import logging

from .models import GPUServer, GPUInfo

task_logger = logging.getLogger('django.task')


def ssh_execute(host, user, exec_cmd, private_key_path=None):
    if private_key_path is None:
        cmd = "ssh -o StrictHostKeyChecking=no {}@{} \"{}\"".format(user, host, exec_cmd)
    else:
        cmd = "ssh -o StrictHostKeyChecking=no -i {} {}@{} \"{}\"".format(private_key_path, user, host, exec_cmd)
    return subprocess.check_output(cmd, timeout=60, shell=True)


def get_hostname(host, user, private_key_path=None):
    cmd = "hostname"
    return str(ssh_execute(
        host,
        user,
        cmd,
        private_key_path
    ).replace(b'\n', b'')).replace('b\'', '').replace('\'', '')


def add_hostname(server, user, private_key_path=None):
    hostname = get_hostname(server.ip, user, private_key_path)
    server.hostname = hostname
    server.save()


def get_gpu_info(host, user, gpustat_path, private_key_path=None):
    return json.loads(ssh_execute(
        host,
        user,
        '{} --json'.format(gpustat_path),
        private_key_path
    ).replace(b'\n', b''))


class GPUInfoUpdater:
    def __init__(self, user, gpustat_path, private_key_path=None):
        self.user = user
        self.private_key_path = private_key_path
        self.gpustat_path = gpustat_path
        self.utilization_history = {}
    
    def update_utilization(self, uuid, utilization):
        if self.utilization_history.get(uuid) is None:
            self.utilization_history[uuid] = [utilization]
            return utilization
        else:
            self.utilization_history[uuid].append(utilization)
            if len(self.utilization_history[uuid]) > 10:
                self.utilization_history[uuid].pop(0)
            return max(self.utilization_history[uuid])

    def update_gpu_info(self):
        server_list = GPUServer.objects.all()
        for server in server_list:
            try:
                if server.hostname is None or server.hostname == '':
                    add_hostname(server, self.user, self.private_key_path)
                gpu_info_json = get_gpu_info(server.ip, self.user, self.gpustat_path, self.private_key_path)
                if not server.valid:
                    server.valid = True
                    server.save()
                for gpu in gpu_info_json['gpus']:
                    if GPUInfo.objects.filter(uuid=gpu['uuid']).count() == 0:
                        gpu_info = GPUInfo(
                            uuid=gpu['uuid'],
                            name=gpu['name'],
                            index=gpu['index'],
                            utilization=self.update_utilization(gpu['uuid'], gpu['utilization.gpu']),
                            memory_total=gpu['memory.total'],
                            memory_used=gpu['memory.used'],
                            processes='\n'.join(map(lambda x: json.dumps(x), gpu['processes'])),
                            complete_free=len(gpu['processes']) == 0,
                            server=server
                        )
                        gpu_info.save()
                    else:
                        gpu_info = GPUInfo.objects.get(uuid=gpu['uuid'])
                        gpu_info.utilization = self.update_utilization(gpu['uuid'], gpu['utilization.gpu'])
                        gpu_info.memory_total = gpu['memory.total']
                        gpu_info.memory_used = gpu['memory.used']
                        gpu_info.complete_free = len(gpu['processes']) == 0
                        gpu_info.processes = '\n'.join(map(lambda x: json.dumps(x), gpu['processes']))
                        gpu_info.save()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                task_logger.error('Update ' + server.ip + ' failed')
                server.valid = False
                server.save()
