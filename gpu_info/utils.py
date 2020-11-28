import os
import subprocess
import json

from .models import GPUServer, GPUInfo


def get_hostname(user, host):
    cmd = "hostname"
    return str(subprocess.check_output(
        "ssh " + user + "@" + host + " \"" + cmd + "\"",
        shell=True
    ).replace(b'\n', b'')).replace('b\'', '').replace('\'', '')


def add_server(username, ip):
    hostname = get_hostname(username, ip)
    server = GPUServer(ip=ip, hostname=hostname) 
    server.save()


def get_gpu_info(user, host, gpustat_path):
    return json.loads(subprocess.check_output(
        "ssh " + user + "@" + host + " \"" + gpustat_path + " --json\"",
        shell=True
    ).replace(b'\n', b''))


class GPUInfoUpdater:
    def __init__(self, username, gpustat_path):
        self.username = username
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
                gpu_info_json = get_gpu_info(self.username, server.ip, self.gpustat_path)
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
            except subprocess.CalledProcessError:
                print('Update ' + server.ip + ' failed')
                server.valid = False
                server.save()
