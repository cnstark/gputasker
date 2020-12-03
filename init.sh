# 安装库
pip install django django-simpleui
# 更新数据库对象
python manage.py makemigrations
python manage.py migrate
# 创建管理员
python manage.py createsuperuser