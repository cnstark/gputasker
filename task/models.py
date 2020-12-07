import os
import signal

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from gpu_info.models import GPUServer, GPUInfo
from django.contrib.auth.models import User


class GPUTask(models.Model):
    STATUS_CHOICE = (
        (-2, '未就绪'),
        (-1, '运行失败'),
        (0, '准备就绪'),
        (1, '运行中'),
        (2, '已完成'),
    )
    name = models.CharField('任务名称', max_length=100)
    user = models.ForeignKey(User, verbose_name='用户', on_delete=models.CASCADE, related_name='tasks')
    workspace = models.CharField('工作目录', max_length=200)
    cmd = models.TextField('命令')
    gpu_requirement = models.PositiveSmallIntegerField(
        'GPU数量需求',
        default=1,
        validators=[MaxValueValidator(8), MinValueValidator(0)]
    )
    exclusive_gpu = models.BooleanField('独占显卡', default=False)
    memory_requirement = models.PositiveSmallIntegerField('显存需求(MB)', default=0)
    utilization_requirement = models.PositiveSmallIntegerField('利用率需求(%)', default=0)
    assign_server = models.ForeignKey(GPUServer, verbose_name='指定服务器', on_delete=models.CASCADE, blank=True, null=True)
    priority = models.SmallIntegerField('优先级', default=0)
    status = models.SmallIntegerField('状态', choices=STATUS_CHOICE, default=0)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'GPU任务'
        verbose_name_plural = 'GPU任务'

    def __str__(self):
        return self.name

    def find_available_server(self):
        # TODO(Yuhao Wang): 优化算法，找最优server
        available_server = None
        if self.assign_server is None:
            for server in GPUServer.objects.all():
                available_gpus = server.get_available_gpus(
                    self.gpu_requirement,
                    self.exclusive_gpu,
                    self.memory_requirement,
                    self.utilization_requirement
                )
                if available_gpus is not None:
                    available_server = {
                        'server': server,
                        'gpus': available_gpus[:self.gpu_requirement]
                    }
                    break
        else:
            available_gpus = self.assign_server.get_available_gpus(
                self.gpu_requirement,
                self.exclusive_gpu,
                self.memory_requirement,
                self.utilization_requirement
            )
            if available_gpus is not None:
                available_server = {
                    'server': self.assign_server,
                    'gpus': available_gpus[:self.gpu_requirement]
                }

        return available_server


class GPUTaskRunningLog(models.Model):
    STATUS_CHOICE = (
        (-1, '运行失败'),
        (1, '运行中'),
        (2, '已完成'),
    )
    index = models.PositiveSmallIntegerField('序号')
    task = models.ForeignKey(GPUTask, verbose_name='任务', on_delete=models.CASCADE, related_name='task_logs')
    server = models.ForeignKey(GPUServer, verbose_name='服务器', on_delete=models.CASCADE, related_name='task_logs')
    pid = models.IntegerField('PID')
    gpus = models.CharField('GPU', max_length=20)
    log_file_path = models.FilePathField(path='running_log', match='.*\.log$', verbose_name="日志文件")
    status = models.SmallIntegerField('状态', choices=STATUS_CHOICE, default=1)
    start_at = models.DateTimeField('开始时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ('-id',)
        verbose_name = 'GPU任务运行记录'
        verbose_name_plural = 'GPU任务运行记录'

    def __str__(self):
        return self.task.name + '-' + str(self.index)

    def kill(self):
        os.kill(self.pid, signal.SIGKILL)
    
    def delete_log_file(self):
        if os.path.isfile(self.log_file_path):
            os.remove(self.log_file_path)
