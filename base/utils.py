from django.contrib.auth.models import User
from .models import SystemConfig


def get_admin_config():
    admin_users = User.objects.filter(is_superuser=True)
    system_config = SystemConfig.objects.all()
    if admin_users.count() == 0:
        raise RuntimeError('Please create a superuser!')
    if system_config.count() == 0:
        raise RuntimeError('Please login admin site and set system config!')
    elif system_config.count() != 1:
        raise RuntimeError('Please login admin site and delete other system config!')
    if system_config[0].user.config is None:
        raise RuntimeError(
            'Please login admin site and create a config for user {}!'.format(system_config[0].user.username)
        )
    return system_config[0].user.config.server_username, \
        system_config[0].user.config.server_private_key_path, \
        system_config[0].gpustat_path
