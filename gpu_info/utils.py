import os
import subprocess
import json
import logging

from .models import GPUServer, GPUInfo

task_logger = logging.getLogger('django.task')


def ssh_execute(host, user, exec_cmd, port=22, private_key_path=None):
    exec_cmd = exec_cmd.replace('\r\n', '\n').replace('$', '\\$')
    if exec_cmd[-1] != '\n':
        exec_cmd = exec_cmd + '\n'
    if private_key_path is None:
        cmd = "ssh -o StrictHostKeyChecking=no -p {:d} {}@{} \"{}\"".format(port, user, host, exec_cmd)
    else:
        cmd = "ssh -o StrictHostKeyChecking=no -p {:d} -i {} {}@{} \"{}\"".format(port, private_key_path, user, host, exec_cmd)
    return subprocess.check_output(cmd, timeout=60, shell=True)


def get_hostname(host, user, port=22, private_key_path=None):
    cmd = "hostname"
    return str(ssh_execute(
        host,
        user,
        cmd,
        port,
        private_key_path
    ).replace(b'\n', b'')).replace('b\'', '').replace('\'', '')


def add_hostname(server, user, private_key_path=None):
    hostname = get_hostname(server.ip, user, server.port, private_key_path)
    server.hostname = hostname
    server.save()


def get_gpu_status(host, user, port=22, private_key_path=None):
    gpu_info_list = []
    query_gpu_cmd = 'nvidia-smi --query-gpu=uuid,gpu_name,utilization.gpu,memory.total,memory.used --format=csv | grep -v \'uuid\''
    gpu_info_raw = ssh_execute(host, user, query_gpu_cmd, port, private_key_path).decode('utf-8')

    if gpu_info_raw.find('Error') != -1:
        raise RuntimeError(gpu_info_raw)

    gpu_info_dict = {}
    for index, gpu_info_line in enumerate(gpu_info_raw.split('\n')):
        try:
            gpu_info_items = gpu_info_line.split(',')
            gpu_info = {}
            gpu_info['index'] = index
            gpu_info['uuid'] = gpu_info_items[0].strip()
            gpu_info['name'] = gpu_info_items[1].strip()
            gpu_info['utilization.gpu'] = int(gpu_info_items[2].strip().split(' ')[0])
            gpu_info['memory.total'] = int(gpu_info_items[3].strip().split(' ')[0])
            gpu_info['memory.used'] = int(gpu_info_items[4].strip().split(' ')[0])
            gpu_info['processes'] = []
            gpu_info_list.append(gpu_info)
            gpu_info_dict[gpu_info['uuid']] = gpu_info
        except Exception:
            continue

    pid_set = set([])
    if len(gpu_info_list) != 0:
        query_apps_cmd = 'nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv'
        app_info_raw = ssh_execute(host, user, query_apps_cmd, port, private_key_path).decode('utf-8')

        for app_info_line in app_info_raw.split('\n')[1:]:
            try:
                app_info_items = app_info_line.split(',')
                app_info = {}
                uuid = app_info_items[0].strip()
                app_info['pid'] = int(app_info_items[1].strip())
                app_info['command'] = app_info_items[2].strip()
                app_info['gpu_memory_usage'] = int(app_info_items[3].strip().split(' ')[0])
                if app_info['gpu_memory_usage'] != 0:
                    gpu_info_dict[uuid]['processes'].append(app_info)
                    pid_set.add(app_info['pid'])
            except Exception:
                continue

    pid_username_dict = {}
    if len(pid_set) != 0:
        try:
            query_pid_cmd = 'ps -o ruser=userForLongName -o pid -p ' + ' '.join(map(str, pid_set)) + ' | awk \'{print $1, $2}\' | grep -v \'PID\''
            pid_raw = ssh_execute(host, user, query_pid_cmd, port, private_key_path).decode('utf-8')
            for pid_line in pid_raw.split('\n'):
                try:
                    username, pid = pid_line.split(' ')
                    pid = int(pid.strip())
                    pid_username_dict[pid] = username.strip()
                except Exception:
                    continue
        except Exception:
            pass
    for gpu_info in gpu_info_list:
        for process in gpu_info['processes']:
            process['username'] = pid_username_dict.get(process['pid'], '')

    return gpu_info_list


class GPUInfoUpdater:
    def __init__(self, user, private_key_path=None):
        self.user = user
        self.private_key_path = private_key_path
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
                gpu_info_json = get_gpu_status(server.ip, self.user, server.port, self.private_key_path)
                if not server.valid:
                    server.valid = True
                    server.save()
                for gpu in gpu_info_json:
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
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError):
                task_logger.error('Update ' + server.ip + ' failed')
                server.valid = False
                server.save()
