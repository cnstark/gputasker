from django.contrib import admin
from django.utils.html import format_html
from .models import GPUTask, GPUTaskRunningLog


@admin.register(GPUTask)
class GPUTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'workspace', 'cmd', 'gpu_requirement', 'memory_requirement', 'utilization_requirement', 'assign_server', 'priority', 'color_status', 'create_at',)
    list_filter = ('gpu_requirement', 'status', 'assign_server', 'priority')
    search_fields = ('name', 'status',)
    list_display_links = ('name',)
    readonly_fields = ('create_at',)
    actions = ('copy_task', 'restart_task',)

    def has_add_permission(self, request):
        return True

    def color_status(self, obj):
        if obj.status == -2:
            status = '未就绪'
            color_code = 'gray'
        elif obj.status == -1:
            status = '运行失败'
            color_code = 'red'
        elif obj.status == 0:
            status = '准备就绪'
            color_code = 'blue'
        elif obj.status == 1:
            status = '运行中'
            color_code = '#ecc849'
        elif obj.status == 2:
            status = '已完成'
            color_code = 'green'
        else:
            status = '未知状态'
            color_code = 'red'
        return format_html('<span style="color:{};">{}</span>', color_code, status)

    color_status.short_description = '状态'
    color_status.admin_order_field = 'status'

    def delete_queryset(self, request, queryset):
        for task in queryset:
            for running_task in task.task_logs.all():
                running_task.delete_log_file()
            task.delete()

    def copy_task(self, request, queryset):
        for task in queryset:
            new_task = GPUTask(
                name=task.name + '_copy',
                workspace=task.workspace,
                cmd=task.cmd,
                gpu_requirement=task.gpu_requirement,
                memory_requirement=task.memory_requirement,
                utilization_requirement=task.utilization_requirement,
                assign_server=task.assign_server,
                priority=task.priority,
                status=-2
            )
            new_task.save()

    copy_task.short_description = '复制任务'
    copy_task.icon = 'el-icon-document-copy'
    copy_task.type = 'success'

    def restart_task(self, request, queryset):
        for task in queryset:
            task.status = 0
            task.save()

    restart_task.short_description = '重新开始'
    restart_task.icon = 'el-icon-refresh-left'
    restart_task.type = 'success'


@admin.register(GPUTaskRunningLog)
class GPUTaskRunningLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'index', 'task', 'server', 'gpus', 'log_file_path', 'color_status', 'start_at', 'update_at',)
    list_filter = ('task', 'server', 'status')
    search_fields = ('task', 'server',)
    list_display_links = ('task',)
    readonly_fields = ('start_at', 'update_at', 'log', 'task', 'index', 'server', 'gpus', 'status', 'log_file_path', 'pid')
    fieldsets = (
        ('基本信息', {'fields': ['task', 'index', 'server', 'gpus', 'pid']}),
        ('状态信息', {'fields': ['status', 'start_at', 'update_at']}),
        ('日志', {'fields': ['log_file_path', 'log']})
    )
    actions = ('kill_button',)

    def has_add_permission(self, request):
        return False

    def delete_queryset(self, request, queryset):
        for running_task in queryset:
            running_task.delete_log_file()
            running_task.delete()
    
    def color_status(self, obj):
        if obj.status == -1:
            status = '运行失败'
            color_code = 'red'
        elif obj.status == 1:
            status = '运行中'
            color_code = '#ecc849'
        elif obj.status == 2:
            status = '已完成'
            color_code = 'green'
        else:
            status = '未知状态'
            color_code = 'red'
        return format_html('<span style="color:{};">{}</span>', color_code, status)

    color_status.short_description = '状态'
    color_status.admin_order_field = 'status'

    def log(self, obj):
        try:
            with open(obj.log_file_path, 'r') as f:
                return f.read()
        except Exception:
            return 'Error: Cannot open log file'

    log.short_description = '日志'

    def kill_button(self, request, queryset):
        for running_task in queryset:
            if running_task.status == 1:
                running_task.kill()

    kill_button.short_description = '结束进程'
    kill_button.icon = 'el-icon-error'
    kill_button.type = 'danger'
    kill_button.confirm = '是否执意结束选中进程？'

