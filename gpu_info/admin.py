from django.contrib import admin
from .models import GPUServer, GPUInfo


@admin.register(GPUServer)
class GPUServerAdmin(admin.ModelAdmin):
    list_display = ('ip', 'hostname', 'valid', 'can_use')
    list_editable = ('can_use',)
    search_fields = ('ip', 'hostname', 'valid', 'can_use')
    list_display_links = ('ip',)
    ordering = ('ip',)
    readonly_fields = ('ip', 'hostname',)

    def has_add_permission(self, request):
        return False


@admin.register(GPUInfo)
class GPUInfoAdmin(admin.ModelAdmin):
    list_display = ('index', 'name', 'utilization', 'memory_usage', 'server', 'free', 'complete_free', 'update_at')
    list_filter = ('server', 'name', 'free', 'complete_free')
    search_fields = ('uuid', 'name', 'memory_used', 'server',)
    list_display_links = ('name',)
    ordering = ('server', 'index')
    readonly_fields = ('uuid', 'name', 'index', 'utilization', 'memory_total', 'memory_used','server', 'processes', 'free', 'complete_free', 'update_at')

    def has_add_permission(self, request):
        return False

    def memory_usage(self, obj):
        memory_total = obj.memory_total
        memory_used = obj.memory_used
        return '{:d} / {:d} MB ({:.0f}%)'.format(memory_used, memory_total, memory_used / memory_total * 100)
    
    memory_usage.short_description = '显存占用率'
