from django.contrib.auth.models import User


def get_admin_config():
    admin_users = User.objects.filter(is_superuser=True)
    if admin_users.count() == 0:
        raise RuntimeError('Please create a superuser!')

    if admin_users[0].config is None:
        raise RuntimeError(
            'Please login admin site and create a config for user {}!'.format(admin_users[0].username)
        )
    return admin_users[0].config.server_username, admin_users[0].config.server_private_key_path
