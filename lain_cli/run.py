# -*- coding: utf-8 -*-
import os
from jinja2 import Environment
import subprocess
from argh.decorators import arg
from six import iteritems

from lain_sdk.util import info, mkdir_p
from lain_sdk.yaml.conf import DOCKER_APP_ROOT
from lain_cli.utils import lain_yaml


LOCAL_VOLUME_BASE = "/tmp/lain/run"
LOCAL_COMPOSE_FILE_BASE = "/tmp/lain/compose"


TMPL_COMPOSE = '''\
version: '2'
services:
{% for service in services %}\
    {{ service.service_name }}:
        image: "{{ service.image }}"
        command: {{ service.cmd }}
        working_dir: {{ service.working_dir }}
{% if service.ports %}\
        ports:
{% for port in service.ports %}\
            - "{{ port }}"
{% endfor %}\
{% endif %}\
{% if service.envs %}\
        environment:
{% for env in service.envs %}\
            - {{ env }}
{% endfor %}\
{% endif %}\
{% if service.volumes %}\
        volumes:
{% for volume in service.volumes %}\
            - {{ volume }}
{% endfor %}\
{% endif %}\
{% if depends %}\
        depends_on:
{% if redis %}\
            - redis
{% endif %}\
{% if mysql %}\
            - mysql
{% endif %}\
{% endif %}\
{% endfor %}\
{% if redis %}\
    redis:
        image: "redis:3.2.7"
{% endif %}\
{% if mysql %}\
    mysql:
        image: mysql:5.6.35
        command: --character-set-server=utf8 --collation-server=utf8_unicode_ci
        environment:
            MYSQL_ROOT_PASSWORD: root
            MYSQL_DATABASE: {{ appname }}
{% endif %}\
'''


def gen_compose_file_path(appname):
    path = '{}/{}'.format(LOCAL_COMPOSE_FILE_BASE, appname)
    file_path = '{}/docker-compose.yaml'.format(path)
    mkdir_p(path)
    return file_path


def gen_compose_file(appname, **params):
    compose_file = gen_compose_file_path(appname)
    with open(compose_file, 'w') as f:
        f.write(Environment().from_string(TMPL_COMPOSE).render(**params))
    return compose_file


def gen_run_ctx():
    ctx = []
    yml = lain_yaml(ignore_prepare=True)
    for proc in yml.procs.values():
        full_proc_name = "{}.{}.{}".format(yml.appname, proc.type.name, proc.name)
        service_name = "{}.{}".format(proc.type.name, proc.name)
        image = yml.img_names['release']
        ports = list(proc.port.keys()) if proc.port.keys() else None
        working_dir = proc.working_dir or DOCKER_APP_ROOT
        cmd = proc.cmd
        env = proc.env
        extra_env = [
            'TZ=Asia/Shanghai',
            'LAIN_RUN_MODE=sdk',
            'LAIN_APPNAME={}'.format(yml.appname),
            'LAIN_PROCNAME={}'.format(proc.name),
            'LAIN_DOMAIN=lain.local',
            'DEPLOYD_POD_INSTANCE_NO=1',
            'DEPLOYD_POD_NAME={}'.format(full_proc_name),
            'DEPLOYD_POD_NAMESPACE={}'.format(yml.appname)
        ]
        envs = env + extra_env
        volumes = {}
        local_proc_volume_base = os.path.join(LOCAL_VOLUME_BASE, full_proc_name)
        if proc.volumes:
            for v in proc.volumes:
                container_path = os.path.join(local_proc_volume_base, v)
                host_path = local_proc_volume_base + container_path
                volumes[host_path] = container_path
        proc_volumes = []
        for (k, v) in iteritems(volumes):
            proc_volumes.append('{}:{}'.format(k, v))

        proc_params = dict(
            service_name=service_name,
            full_proc_name=full_proc_name,
            image=image,
            working_dir=working_dir,
            cmd=cmd,
            ports=ports,
            envs=envs or [],
            volumes=proc_volumes,
        )
        ctx.append(proc_params)
    return yml.appname, ctx


def _compose(redis, mysql, verbose):
    appname, ctx = gen_run_ctx()
    params = dict(
        services=ctx,
        depends=redis or mysql,
        redis=redis,
        mysql=mysql
    )
    compose_file = gen_compose_file(appname, **params)
    if verbose:
        print(compose_file)
        subprocess.call(['cat', compose_file])
    return compose_file


@arg('--redis', help="depend on redis")
@arg('--mysql', help="depend on mysql")
@arg('-v', '--verbose', help="more infomation")
def run(redis=False, mysql=False, verbose=False):
    """
    Run app in the local host with docker-compose
    """

    compose_file = _compose(redis, mysql, verbose)
    subprocess.check_call(['docker-compose', '-f', compose_file, 'up', '-d'])


@arg('-f', '--follow', help="keep following logs")
def logs(follow=False):
    """
    Tailing logs of app in the local host
    """
    yml = lain_yaml(ignore_prepare=True)
    compose_file = gen_compose_file_path(yml.appname)
    cmds = ['docker-compose', '-f', compose_file, 'logs']
    if follow:
        cmds.append('-f')
    subprocess.check_call(cmds)


def stop():
    """
    Stop app in the local host
    """

    yml = lain_yaml(ignore_prepare=True)
    compose_file = gen_compose_file_path(yml.appname)
    subprocess.check_call(['docker-compose', '-f', compose_file, 'down'])
