FROM python:3.9

RUN apt update && \
    apt install -y openssh-client && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install django django-simpleui mysqlclient uwsgi && \
    rm -r /root/.cache/pip

ENV DOCKER_DEPLOY 1

ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /

ADD . /gpu_tasker

WORKDIR /gpu_tasker

RUN chmod +x /wait-for-it.sh && \
    chmod +x entrypoint.sh

VOLUME /gpu_tasker/server_log
VOLUME /gpu_tasker/running_log
VOLUME /gpu_tasker/private_key
VOLUME /gpu_tasker/static_collected
VOLUME /gpu_tasker/uwsgi/log

EXPOSE 9009

ENTRYPOINT ["/wait-for-it.sh", "mariadb:3306", "-t", "180", "--", "./entrypoint.sh"]
