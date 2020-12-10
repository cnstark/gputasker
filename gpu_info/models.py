import json

from django.db import models


class GPUServer(models.Model):
    ip = models.CharField('IP地址', max_length=50, primary_key=True)
    hostname = models.CharField('主机名', max_length=50, blank=True, null=True)
    valid = models.BooleanField('是否可用', default=True)
    can_use = models.BooleanField('是否可调度', default=True)
    # TODO(Yuhao Wang): CPU使用率

    class Meta:
        ordering = ('ip',)
        verbose_name = 'GPU服务器'
        verbose_name_plural = 'GPU服务器'

    def __str__(self):
        return self.ip

    def get_available_gpus(self, gpu_num, exclusive, memory, utilization):
        available_gpu_list = []
        if self.valid and self.can_use:
            for gpu in self.gpus.all():
                if gpu.check_available(exclusive, memory, utilization):
                    available_gpu_list.append(gpu.index)
            if len(available_gpu_list) >= gpu_num:
                return available_gpu_list
            else:
                return None
        else:
            return None
    
    def set_gpus_busy(self, gpu_list):
        self.gpus.filter(index__in=gpu_list).update(use_by_self=True)

    def set_gpus_free(self, gpu_list):
        self.gpus.filter(index__in=gpu_list).update(use_by_self=False)


class GPUInfo(models.Model):
    uuid = models.CharField('UUID', max_length=40, primary_key=True)
    index = models.PositiveSmallIntegerField('序号')
    name = models.CharField('名称', max_length=40)
    utilization = models.PositiveSmallIntegerField('利用率')
    memory_total = models.PositiveIntegerField('总显存')
    memory_used = models.PositiveIntegerField('已用显存')
    processes = models.TextField('进程')
    server = models.ForeignKey(GPUServer, verbose_name='服务器', on_delete=models.CASCADE, related_name='gpus')
    use_by_self = models.BooleanField('是否被gputasker进程占用', default=False)
    complete_free = models.BooleanField('完全空闲', default=False)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ('server', 'index',)
        verbose_name = 'GPU信息'
        verbose_name_plural = 'GPU信息'

    def __str__(self):
        return self.name + '[' + str(self.index) + '-' + self.server.ip + ']'
    
    @property
    def memory_available(self):
        return self.memory_total - self.memory_used

    @property
    def utilization_available(self):
        return 100 - self.utilization

    def check_available(self, exclusive, memory, utilization):
        if exclusive:
            return not self.use_by_self and self.complete_free
        else:
            return not self.use_by_self and self.memory_available > memory and self.utilization_available > utilization

    def usernames(self):
        r"""
        convert processes string to usernames string array.
        :return: string array of usernames.
        """
        if self.processes != '':
            arr = self.processes.split('\n')
            # only show first two usernames
            username_arr = [json.loads(item)['username'] for item in arr[:2]]
            res = ', '.join(username_arr)
            # others use ... to note
            if len(arr) > 2:
                res = res + ', ...'
            return res
        else:
            return '-'
