from django.db import models


class GPUServer(models.Model):
    ip = models.GenericIPAddressField('IP地址', protocol='IPv4', primary_key=True)
    hostname = models.CharField('主机名', max_length=10)
    valid = models.BooleanField('是否可用', default=True)
    can_use = models.BooleanField('是否可调度', default=True)
    # TODO(Yuhao Wang): CPU使用率

    class Meta:
        ordering = ('ip',)
        verbose_name = 'GPU服务器'
        verbose_name_plural = 'GPU服务器'

    def __str__(self):
        return self.ip

    def get_available_gpus(self, gpu_num, memory, utilization):
        available_gpu_list = []
        if self.valid and self.can_use:
            for gpu in self.gpus.all():
                if gpu.check_available(memory, utilization):
                    available_gpu_list.append(gpu.index)
            if len(available_gpu_list) >= gpu_num:
                return available_gpu_list
            else:
                return None
        else:
            return None
    
    def set_gpus_busy(self, gpu_list):
        self.gpus.filter(index__in=gpu_list).update(free=False)

    def set_gpus_free(self, gpu_list):
        self.gpus.filter(index__in=gpu_list).update(free=True)


class GPUInfo(models.Model):
    uuid = models.CharField('UUID', max_length=40, primary_key=True)
    index = models.PositiveSmallIntegerField('序号')
    name = models.CharField('名称', max_length=40)
    utilization = models.PositiveSmallIntegerField('利用率')
    memory_total = models.PositiveIntegerField('总显存')
    memory_used = models.PositiveIntegerField('已用显存')
    processes = models.TextField('进程')
    server = models.ForeignKey(GPUServer, verbose_name='服务器', on_delete=models.CASCADE, related_name='gpus')
    free = models.BooleanField('是否可用', default=True)
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

    def check_available(self, memory, utilization):
        return self.free and self.memory_available > memory and self.utilization_available > utilization
