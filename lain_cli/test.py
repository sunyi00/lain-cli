import os
import subprocess
import sys

import lain_sdk
from argh.decorators import arg
from jinja2 import Environment
from lain_cli.utils import lain_yaml
from lain_sdk.mydocker import copy_file_from_container
from lain_sdk.util import meta_version, rm

TMPL_COMPOSE = '''\
version: '2'
services:
    app:
        image: "{{ image }}"
        command: sh lain-test.sh
{% if envs %}\
        environment:
{% for env in envs %}\
            - {{ env }}
{% endfor %}\
{% endif %}\
        volumes:
            - ./lain-test.sh:/lain/app/lain-test.sh
{% for volume in volumes %}\
            - {{ volume }}
{% endfor %}\
{% if depends %}\
        depends_on:
            - redis
            - mysql
            - minio
    redis:
        image: "redis:3.2.7"
    mysql:
        image: mysql:5.6.35
        command: --character-set-server=utf8 --collation-server=utf8_unicode_ci
        environment:
            MYSQL_ROOT_PASSWORD: root
            MYSQL_DATABASE: {{ appname }}
    minio:
        image: "minio/minio:RELEASE.2018-05-16T23-35-33Z"
        command: server /data
        environment:
            MINIO_ACCESS_KEY: TESTACCESSKEY
            MINIO_SECRET_KEY: TESTSECRETKEY
{% endif %}
'''

TMPL_SCRIPT = '''
#!/bin/bash
set -xe
{% for s in scripts %}
{{ s }}
{% endfor %}
'''

RUN_COMPOSE_FILE = './docker-compose.yml'
TPL_COMPOSE_FILE = './docker-compose.yml.j2'


def gen_compose_file(**params) -> str:
    """
    Return docker-compose filename
    """
    template_str = TMPL_COMPOSE
    if os.path.isfile(TPL_COMPOSE_FILE):
        print("A custom docker-compose.yml template is detected")
        with open(TPL_COMPOSE_FILE, 'r') as f:
            template_str = f.read()
    with open(RUN_COMPOSE_FILE, 'w') as f:
        f.write(Environment().from_string(template_str).render(**params))


def gen_test_script(**params):
    with open('./lain-test.sh', 'w') as f:
        f.write(Environment().from_string(TMPL_SCRIPT).render(**params))


def clear():
    try:
        rm(RUN_COMPOSE_FILE)
    except Exception:
        pass
    try:
        rm('./lain-test.sh')
    except Exception:
        pass


def clear_test_result():
    try:
        rm('./cobertura.xml')
    except Exception:
        pass
    try:
        rm('./testresult.xml')
    except Exception:
        pass


def _test(simple, envs, volumes, results):
    x = lain_yaml()
    appname = x.appname
    scripts = x.test.script
    container = "{}_app".format(appname)
    clear()
    clear_test_result()
    subprocess.call(['lain', 'clear', '--without', 'prepare'])

    # test with docker-compose
    test_pass = False
    try:
        subprocess.call(['lain', 'build'])
        build_postfix = ''
        v_list = [v for v in lain_sdk.__version__.split('.')]
        v1, v2 = int(v_list[0]), int(v_list[1])
        if v1 == 2 and v2 >= 3:
            build_postfix = '-{}'.format(meta_version('.'))
        elif v1 > 2:
            build_postfix = '-{}'.format(meta_version('.'))
        image = f"{appname}:build{build_postfix}"
        gen_compose_file(
            appname=appname,
            image=image,
            envs=envs or [],
            volumes=volumes or [],
            depends=not simple,
        )
        gen_test_script(scripts=scripts)
        subprocess.check_call([
            'docker-compose',
            'run',
            '--name',
            container,
            'app',
        ])
        if results:
            for result in results:
                copy_file_from_container(container, result)
        test_pass = True
    except Exception as e:
        print("TEST FAILED")
        print(e)
    finally:
        subprocess.call(['docker-compose', 'down'])

    clear()
    return test_pass


@arg('-s', '--simple', help="simple mode without redis, mysql or minio")
@arg('-e', '--envs', nargs='*')
@arg('-v', '--volumes', nargs='*')
@arg('-r', '--results', nargs='*', type=str)
def test(simple=False,
         envs=None,
         volumes=None,
         results=["cobertura.xml", "testresult.xml"]):
    """
    Build test image and run test scripts defined in lain.yaml
    """

    test_pass = _test(simple, envs, volumes, results)
    if test_pass:
        sys.exit(0)
    else:
        sys.exit(1)
