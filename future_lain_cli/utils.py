import base64
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from inspect import cleandoc
from os import getcwd, readlink, remove
from os.path import abspath, basename, dirname, expanduser, isdir, isfile, join
from tempfile import NamedTemporaryFile, TemporaryDirectory
from types import MappingProxyType
from urllib.parse import urljoin

import click
import requests
import yaml
from jinja2 import Environment, FileSystemLoader, Template

# safe to delete when release is in this state
HELM_WEIRD_STATE = {'failed', 'pending-install'}
CLI_DIR = dirname(abspath(__file__))
TEMPLATE_DIR = join(CLI_DIR, 'chart_template')
template_env = Environment(loader=FileSystemLoader(searchpath=TEMPLATE_DIR))
CHART_DIR_NAME = 'chart'
ENV = os.environ
LAIN_EXBIN_PREFIX = ENV.get('LAIN_EXBIN_PREFIX') or '/usr/local/bin'
HELM_BIN = join(LAIN_EXBIN_PREFIX, 'helm')
KUBECTL_BIN = join(LAIN_EXBIN_PREFIX, 'kubectl')
CDN = 'https://static.einplus.cn'
ENV['PATH'] = f'{LAIN_EXBIN_PREFIX}:{ENV["PATH"]}'
FUTURE_CLUSTERS = MappingProxyType({
    'future': MappingProxyType({
        'legacy_lain_phase': 'ein',  # this tells lain4 where to push your image
        'legacy_lain_domain': 'lain.ein.plus',
        'registry': 'registry.lain.ein.plus',
        'grafana_url': 'http://grafana.future.ein.plus/d/7sl4vJAZk/docker-monitoring',
        'kibana': 'kibana.future.ein.plus',
    }),
    'bei': MappingProxyType({
        'legacy_lain_phase': 'test',
        'legacy_lain_domain': 'poc.ein.plus',
        'registry': 'registry.dev.ein.plus',
    }),
})
LEGACY_CLUSTERS = frozenset({'azure', 'ein', 'poc', 'test'})
CLUSTERS = set(FUTURE_CLUSTERS) | LEGACY_CLUSTERS
LEGACY_IMAGE_PATTERN = re.compile(r'^release-\d+-[^-]+$')
CWD = getcwd()


def quote(s):
    return shlex.quote(s)


def to_yaml(a, *args, **kw):
    '''Make verbose, human readable yaml'''
    transformed = yaml.dump(a, Dumper=yaml.SafeDumper, allow_unicode=True, **kw)
    return transformed


def context():
    return click.get_current_context()


def excall(s, env=None):
    """lain cli often calls other cli, might wanna notify the user what's being
    run"""
    if env:  # reserved for debugging
        env_clause = ' '.join(f'{k}={v}' for k, v in env.items())
        s = f'{env_clause} {s}'

    if not isinstance(s, str):
        s = ' '.join(s)

    click.echo(click.style(s, fg='bright_yellow'), err=True)


def echo(s):
    s = cleandoc(s)
    click.echo(click.style(s))


def goodjob(s, exit=None):
    s = cleandoc(s)
    click.echo(click.style(s, fg='green'))
    if exit:
        context().exit(0)


def error(s, exit=None):
    s = cleandoc(s)
    click.echo(click.style(s, fg='red'))
    if exit is not None:
        context().exit(exit)


deploy_toast_str = '''Your pods have all been created, you can see them using:
    kubectl get po -l app.kubernetes.io/name={{ appname }}

{% if 'ingresses' in values and values.ingresses %}
To access your app through internal domain:
    http://{{ appname }}.{{ cluster }}.ein.plus
{% endif %}
{%- if 'cronjobs' in values and values.cronjobs %}
To test your cronjob:
    {%- for job_name in values.cronjobs.keys() %}
    kubectl create job --from=cronjob/{{ appname }}-{{ job_name }} {{ appname }}-{{ job_name }}-test
    {%- endfor %}

Here's some very good stuff that you'll like:
    {%- if grafana_url %}
    {{ grafana_url }}
    {%- endif %}
    {%- if kibana %}
    http://{{ kibana }}/app/logtrail#/?q=kubernetes.pod_name.keyword:{{ appname }}*&h=All&t=Now&i=logstash-*
    {%- endif %}
{%- endif %}'''
deploy_toast_template = Template(deploy_toast_str)


def deploy_toast():
    ctx = context()
    ctx.obj.update(tell_cluster_info())
    headsup = deploy_toast_template.render(**ctx.obj)
    goodjob(headsup)


class Registry:
    """this client deals with legacy lain registries, it filters out legacy
    data from the registry API"""

    def __init__(self, host):
        self.host = host
        self.base_url = f'http://{host}'

    def request(self, method, path, params=None, data=None, *args, **kwargs):
        url = urljoin(self.base_url, path)
        kwargs.setdefault('timeout', 2)
        res = requests.request(method, url, params=params, data=data, *args, **kwargs)
        return res

    def get(self, url, *args, **kwargs):
        return self.request('GET', url, *args, **kwargs)

    def tags_list(self, repo_name):
        path = f'/v2/{repo_name}/tags/list'
        responson = self.get(path).json()
        tags = [s for s in responson['tags'] if LEGACY_IMAGE_PATTERN.match(s)]
        return sorted(tags, reverse=True)


def clean_kubernetes_manifests(dic):
    """remove irrelevant information from Kubernetes manifests"""
    metadata = dic.get('metadata', {})
    metadata.pop('creationTimestamp', '')
    metadata.pop('selfLink', '')
    metadata.pop('uid', '')
    metadata.pop('resourceVersion', '')
    annotations = metadata.get('annotations', {})
    annotations.pop('kubectl.kubernetes.io/last-applied-configuration', '')


def dump_secret(secret_name, init='env'):
    """create a tempfile and dump plaintext secret into it"""
    secret_dic = tell_secret(secret_name, init=init)
    f = NamedTemporaryFile(suffix='.yaml')
    f.write(yaml.dump(secret_dic).encode('utf-8'))
    return f


def tell_cluster_info():
    ctx = context()
    cluster = ctx.obj['cluster']
    return FUTURE_CLUSTERS[cluster]


def tell_secret(secret_name, init='env'):
    """return Kubernetes secret object in python dict, all b64decoded.
    If secret doesn't exist, create one first, and with some example content"""
    d = TemporaryDirectory()
    if init == 'env':
        init_clause = '--from-literal=FOO=BAR'
    elif init == 'secret':
        example_file = 'topsecret.txt'
        example_file_path = join(d.name, example_file)
        with open(example_file_path, 'w') as f:
            f.write('I\nAM\nBATMAN')

        init_clause = f'--from-file={example_file_path}'
    else:
        raise ValueError(f'init style: env, secret. dont\'t know what this is: {init}')

    kubectl('create', 'secret', 'generic', secret_name, init_clause, capture_output=True)
    d.cleanup()  # don't wanna cleanup too early
    res = kubectl('get', 'secret', '-oyaml', secret_name, capture_output=True, check=True)
    dic = yalo(res.stdout)
    clean_kubernetes_manifests(dic)
    dic.setdefault('data', {})
    for fname, s in dic['data'].items():
        decoded = base64.b64decode(s).decode('utf-8')
        # gotta do this so yaml.dump will print nicely
        dic['data'][fname] = literal(decoded) if '\n' in decoded else decoded

    return dic


def apply_secret(dic):
    """do a b64encode on all data fields, then kubectl apply, easy job"""
    for fname, s in dic['data'].items():
        dic['data'][fname] = base64.b64encode(s.encode('utf-8')).decode('utf-8')

    f = NamedTemporaryFile(suffix='.yaml')
    f.write(yaml.dump(dic).encode('utf-8'))
    f.seek(0)
    kubectl('apply', '-f', f.name, exit=True)


def tell_helm_set_clause(pairs):
    """Sure you can override helm values, but I might not approve it"""
    ctx = context()
    cluster = ctx.obj['cluster']
    registry = FUTURE_CLUSTERS[cluster]['registry']
    # registry and cluster must be provided in a helm deploy command
    sl = [f'registry={registry}', f'cluster={cluster}']
    image_tag = None
    for pair in pairs:
        k, v = pair.popitem()
        if k == 'imageTag':
            v = image_tag = tell_image(v)

        sl.append(f'{k}={v}')

    if not image_tag:
        image_tag = tell_image()
        sl.append(f'imageTag={image_tag}')

    return ','.join(sl)


def tell_image(image_tag=None):
    """really smart method to figure out which image_tag is the right one to deploy:
        1. if image_tag isn't provided, obtain from legacy_lain
        2. check for existence against the specified registry
        3. if image doesn't exist, print helpful suggestions
    """
    if not image_tag:
        image_tag = legacy_lain('meta', capture_output=True).stdout.decode('utf-8').strip()

    if not image_tag.startswith('release-'):
        image_tag = f'release-{image_tag}'

    ctx = context()
    appname = ctx.obj['appname']
    registry = Registry(tell_cluster_info()['registry'])
    existing_tags = registry.tags_list(appname)
    if image_tag not in existing_tags:
        latest_tag = max(existing_tags)
        recent_tags = '\n            '.join(existing_tags[:5])
        err = f'''
        Image not found:
            {registry.host}/{appname}:{image_tag}

        If you really need to deploy this version, do a lain build + push first.
        If you'd like to deploy the latest existing image:
            lain deploy --set imageTag={latest_tag}
        If you'd like to choose an existing image, here's some recent image tags for you to copy:
            {recent_tags}
        You can check out the rest at {registry.base_url}/v2/{appname}/tags/list.
        '''
        error(err)
        ctx.exit(1)

    return image_tag


def legacy_lain(*args, exit=None, fake_lain_yaml=False, **kwargs):
    """sometimes we wanna use chart/values.yaml as LAIN_YAML, this the fake_lain_yaml flag"""
    cmd = ['legacy_lain', *args]
    excall(cmd)
    # use chart/values.yaml as lain.yaml if it exists
    values_yaml = f'./{CHART_DIR_NAME}/values.yaml'
    if not isfile(values_yaml):
        res = subprocess.run(cmd, env=ENV, **kwargs)
    else:
        if fake_lain_yaml:
            # legacy_lain really needs lain.yaml to be in the same directory as the
            # docker build context, yet nobody want to maintain legacy_lain code, so
            # it's easiest to just copy chart/values.yaml into a tempfile
            lain_yaml = NamedTemporaryFile(prefix=f'{CWD}/')
            lain_yaml.write(open(values_yaml, 'rb').read())
            ENV['LAIN_YAML'] = lain_yaml.name

        res = subprocess.run(cmd, env=ENV, **kwargs)

    if exit:
        context().exit(res.returncode)

    return res


def ensure_initiated(chart=False, secret=False):
    ctx = context()
    if chart:
        if not isdir(CHART_DIR_NAME):
            error('helm chart not initialized yet, run `lain init --help` to learn how')
            ctx.exit(1)

    if secret:
        # if volumeMounts are used in values.yaml but secret doesn't exists,
        # print error and then exit
        subPaths = [m['subPath'] for m in ctx.obj['values']['volumeMounts']]
        if subPaths:
            cluster = ctx.obj['cluster']
            res = kubectl('-n', 'default', 'get', 'secret', ctx.obj['secret_name'], capture_output=True)
            if res.returncode:
                tutorial = '\n'.join(f'lain secret add {f}' for f in subPaths)
                err = f'''
                Secret {secret} not found, you should create them:
                    lain use {cluster}
                    {tutorial}
                And if you ever need to add more files, env or edit them, do this:
                    lain secret edit
                '''
                error(err)
                ctx.exit(res.returncode)

    return True


def helm(*args, **kwargs):
    try:
        version_res = subprocess.run(['helm', 'version', '--short'], capture_output=True, check=True)
        version = version_res.stdout.decode('utf-8')
    except FileNotFoundError:
        download_binary('helm', dest=HELM_BIN)
        return helm(*args, **kwargs)
    except PermissionError:
        error(f'Bad binary: {HELM_BIN}, remove it befure use', exit=1)
    if not version.startswith('v3'):
        download_binary('helm', dest=HELM_BIN)
        return helm(*args, **kwargs)
    cmd = ['helm', '-n', 'default', *args]
    excall(cmd)
    completed = subprocess.run(cmd, env=ENV, **kwargs)
    return completed


def kubectl(*args, exit=None, **kwargs):
    try:
        version_res = subprocess.run(['kubectl', 'version', '--short', '--client=true'], capture_output=True, check=True)
        version = version_res.stdout.decode('utf-8').strip().split()[-1]
    except FileNotFoundError:
        download_binary('kubectl', dest=KUBECTL_BIN)
        return kubectl(*args, exit=exit, **kwargs)
    except PermissionError:
        error(f'Bad binary: {KUBECTL_BIN}, remove it befure use', exit=1)
    if version < 'v1.15':
        download_binary('kubectl', dest=KUBECTL_BIN)
        return kubectl(*args, exit=exit, **kwargs)
    env = os.environ
    env['PATH'] = f'{KUBECTL_BIN}:{env["PATH"]}'
    cmd = ['kubectl', *args]
    excall(cmd)
    completed = subprocess.run(cmd, env=env, **kwargs)
    if exit:
        context().exit(completed.returncode)

    return completed


def tell_cluster():
    link = expanduser('~/.kube/config')
    try:
        kubeconfig_file = readlink(link)
    except OSError:
        error(f'{link} is not a symlink, you should delete it and then `lain use [CLUSTER]`', exit=1)
    except FileNotFoundError:
        error(f'{link} not found, you should first `lain use [CLUSTER]`', exit=1)

    name = basename(kubeconfig_file)
    cluster_name = name.split('-', 1)[-1]
    ctx = context()
    ctx.obj['cluster'] = cluster_name
    return cluster_name


def tell_platform():
    platform = sys.platform
    if platform.startswith('darwin'):
        return 'darwin'
    elif platform.startswith('linux'):
        return 'linux'
    error(f'Sorry, never seen this platform: {platform}. Use a Mac or Linux for lain4')
    context().exit(1)


def download_binary(thing, dest):
    assert thing in {'kubectl', 'helm'}
    platform = tell_platform()
    url = f'{CDN}/lain4/{thing}-{platform}'
    click.echo(f'Don\'t mind me, just gonna download {url} into {dest}. If you wanna put them in other places, export LAIN_EXBIN_PREFIX and try this again')
    try:
        with requests.get(url, stream=True) as res:
            with open(dest, 'wb') as f:
                shutil.copyfileobj(res.raw, f)
    except KeyboardInterrupt:
        error(f'Download did not complete, {HELM_BIN} will be cleaned up', exit=1)
        ensure_absent(f)

    # do a `chmod +x` on this thing
    st = os.stat(dest)
    os.chmod(dest, st.st_mode | stat.S_IEXEC)
    autocompletion_tutorial = {
        'kubectl': '''For zsh user, checkout https://github.com/robbyrussell/oh-my-zsh/blob/master/plugins/kubectl/kubectl.plugin.zsh
        Others may learn the same thing at https://kubernetes.io/docs/tasks/tools/install-kubectl/#optional-kubectl-configurations''',
        'helm': '''For zsh user, checkout https://github.com/robbyrussell/oh-my-zsh/tree/master/plugins/helm
        Others go see `helm completion help`'''
    }
    toast = f'''Download complete, you might wanna setup autocompletion for {thing}:
        {autocompletion_tutorial[thing]}'''
    goodjob(toast)


def ensure_absent(path):
    if isfile(path):
        try:
            remove(path)
        except FileNotFoundError:
            pass
    elif isdir(path):
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass


def find(path):
    """mimic to GNU find"""
    for currentpath, folders, files in os.walk(path):
        for file in files:
            abspath = os.path.join(currentpath, file)
            relpath = os.path.relpath(abspath, path)
            yield relpath


def edit_file(f):
    f.seek(0)
    subprocess.call([ENV.get('EDITOR', 'vim'), f.name])
    f.seek(0)


def yalo(f):
    """tired of yaml bitching about unsafe loaders"""
    if hasattr(f, 'read'):
        f = f.read()

    return yaml.load(f, Loader=yaml.FullLoader)


def populate_helm_context(obj):
    """gather basic information about the current app.
    If cluster info is provided, will try to fetch app status from Kubernetes"""
    with open(f'./{CHART_DIR_NAME}/values.yaml') as f:
        helm_values = yalo(f)
        appname = obj['appname'] = helm_values['appname']
        obj['values'] = helm_values

    obj['secret_name'] = f'{appname}-secret'
    obj['env_name'] = f'{appname}-env'


def get_app_status(appname):
    res = helm('status', appname, '-o', 'json', capture_output=True)
    if not res.returncode:
        return json.loads(res.stdout)
    else:
        stderr = res.stderr.decode('utf-8')
        # 'not found' is the only error we can safely ignore
        if 'not found' not in stderr:
            error('helm error during getting app status:')
            error(stderr)
            context().exit(res.returncode)


def populate_helm_context_from_lain_yaml(obj, lain_yaml):
    lain_yaml = yalo(lain_yaml)
    appname = lain_yaml.pop('appname')
    obj['appname'] = appname
    # chart name must be the same as repo dir name
    obj['chart_name'] = CHART_DIR_NAME
    obj['procs'] = {}
    obj['crons'] = {}
    obj['secret_files'] = {}
    for k, clause in lain_yaml.items():
        # 除了 helm charts 关心的部分, 剩下的原样抄写到 values.yaml 里
        # 所以 values.yaml 与 lain.yaml 的并集部分仍然会是一份合法的 lain.yaml
        if k in {'build', 'release', 'test'}:
            obj[k] = clause
        elif k == 'web':
            obj['procs']['web'] = clause
        elif k.startswith('proc.') or k.startswith('worker'):
            proc_name = k.split('.', 1)[-1]
            obj['procs'][proc_name] = clause
        elif k.startswith('cron.'):
            cron_name = k.split('.', 1)[-1]
            obj['crons'][cron_name] = clause
        else:
            raise NotImplementedError(f'{k} clause not handled in the converting process, full lain.yaml: {lain_yaml}')

    for clause in {**obj['procs'], **obj['crons']}.values():
        # shlex all commands
        command = clause.pop('command', None) or clause.pop('cmd', None)
        if command:
            clause['command'] = shlex.split(command) if isinstance(command, str) else command

        # normalize env clause to dict
        envs = clause.get('env', ())
        env_dict = {}
        for env in envs:
            k, v = env.split('=')
            env_dict[k] = v

        clause['env'] = env_dict
        secret_files = clause.pop('secret_files', None)
        # collect all secret_files for easy rendering
        if secret_files:
            for f in secret_files:
                fname = basename(f)
                obj['secret_files'][fname] = f


example_lain_yaml = """# ref: https://github.com/ein-plus/dummy
appname: dummy

build:
  base: registry.lain.ein.plus/einplus/centos-base:20190925-slim
  prepare:
    version: 1
    script:
      - pip3.6 install -U pip -i https://pypi.doubanio.com/simple/
    keep:
      - src
  script:
    - pip3.6 install --exists-action=w -r requirements.txt

web:
  cmd: ['/lain/app/run.py']
  port: 5000
  memory: 80M
  env:
    - FOO=BAR
  secret_files:
    - /lain/app/deploy/topsecret.txt

cron.useless:
  cmd: ['ls']
  memory: 20m
  schedule: "30 0 * * *"
  env:
    - FOO=BAR
  secret_files:
    - /lain/app/deploy/topsecret.txt

test:
  script:
    - make test
"""


template_env.filters['basename'] = basename
template_env.filters['quote'] = quote
template_env.filters['to_yaml'] = to_yaml


class literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(literal, literal_presenter)


class KVPairType(click.ParamType):
    name = "kvpair"

    def convert(self, value, param, ctx):
        try:
            k, v = value.split('=')
            return {k: v}
        except (AttributeError, ValueError):
            self.fail("expected something like FOO=BAR, got " f"{value!r} of type {type(value).__name__}", param, ctx,)
