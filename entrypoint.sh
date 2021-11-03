python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --no-input

uwsgi --ini /gpu_tasker/uwsgi/uwsgi.ini

python main.py
