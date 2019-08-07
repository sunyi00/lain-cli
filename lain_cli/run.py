# -*- coding: utf-8 -*-
import os
import subprocess

from argh.decorators import arg

from jinja2 import Environment
from lain_cli.utils import lain_yaml
from lain_sdk.util import mkdir_p
from lain_sdk.yaml.conf import DOCKER_APP_ROOT
from six import iteritems

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
{% if minio %}\
            - minio
{% endif %}\
{% if elasticsearch %}\
            - elasticsearch
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
{% if minio %}\
    minio:
        image: "minio/minio:RELEASE.2018-05-16T23-35-33Z"
        command: server /data
        environment:
            MINIO_ACCESS_KEY: TESTACCESSKEY
            MINIO_SECRET_KEY: TESTSECRETKEY
{% endif %}\
{% if elasticsearch %}\
    elasticsearch:
        image: "registry.lain.ein.plus/ein-enterprise/elasticsearch:2.4.1-ik-20180906p3"
        command: /bin/bash /run.sh
        environment:
            ES_HEAP_SIZE: 256M
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
        f.write(Environment().from_string(TMPL_COMPOSE).render(appname=appname, **params))
    return compose_file


def merge_kv_list(origins, overrides, splitter='='):
    if not overrides:
        return origins
    kv_dict = {}
    for o in origins:
        name, value = o.strip().split(splitter, 1)
        kv_dict[name] = value
    for r in overrides:
        name, value = r.strip().split(splitter, 1)
        kv_dict[name] = value
    return ["{}{}{}".format(k, splitter, v) for k, v in kv_dict.items()]


def gen_run_ctx(override_envs=None, override_volumes=None):
    ctx = []
    yml = lain_yaml(ignore_prepare=True)
    for proc in yml.procs.values():
        if proc.type.name not in ['web', 'worker']:
            continue
        full_proc_name = "{}.{}.{}".format(yml.appname, proc.type.name, proc.name)
        service_name = "{}.{}".format(proc.type.name, proc.name)
        # FIXME: so rude
        if proc.image.endswith("/" + yml.img_names['release']):
            image = yml.img_names['release']
        else:
            image = proc.image
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
            envs=merge_kv_list(envs, override_envs) or [],
            volumes=merge_kv_list(proc_volumes, override_volumes, splitter=':') or [],
        )
        ctx.append(proc_params)
    return yml.appname, ctx


def _compose(redis, mysql, minio, elasticsearch, envs, volumes):
    appname, ctx = gen_run_ctx(override_envs=envs, override_volumes=volumes)
    params = dict(
        services=ctx,
        depends=redis or mysql or minio or elasticsearch,
        redis=redis,
        mysql=mysql,
        minio=minio,
        elasticsearch=elasticsearch
    )
    compose_file = gen_compose_file(appname, **params)
    print(compose_file)
    subprocess.call(['cat', compose_file])
    return compose_file


@arg('--redis', help="depend on redis")
@arg('--mysql', help="depend on mysql")
@arg('--minio', help="depend on minio")
@arg('--elasticsearch', help="depend on elasticsearch")
@arg('-e', '--envs', nargs='*')
@arg('-v', '--volumes', nargs='*')
def run(redis=False, mysql=False, minio=False, elasticsearch=False, envs=None, volumes=None):
    """
    Run app in the local host with docker-compose

    PRECONDITION:  lain build
    """

    compose_file = _compose(redis, mysql, minio, elasticsearch, envs, volumes)
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
    subprocess.check_call(['docker', 'volume', 'prune', '-f'])
    subprocess.check_call(['docker', 'network', 'prune', '-f'])
