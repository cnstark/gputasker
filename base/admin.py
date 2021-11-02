import os, stat

from django.contrib import admin

from .models import UserConfig
from gpu_tasker.settings import PRIVATE_KEY_DIR


@admin.register(UserConfig)
class UserConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'server_username',)
    search_fields = ('user', 'server_username',)
    list_display_links = ('user',)
    readonly_fields = ('user', 'server_private_key_path',)
    ordering = ('user',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def has_add_permission(self, request):
        return True

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        obj.server_private_key_path = os.path.join(PRIVATE_KEY_DIR, obj.server_username + '_pk')
        # format private key
        obj.server_private_key = obj.server_private_key.replace('\r\n', '\n')
        if obj.server_private_key[-1] != '\n':
            obj.server_private_key = obj.server_private_key + '\n'
        with open(obj.server_private_key_path, 'w') as f:
            f.write(obj.server_private_key)
        os.chmod(obj.server_private_key_path, stat.S_IWUSR | stat.S_IREAD)
        super().save_model(request, obj, form, change)
