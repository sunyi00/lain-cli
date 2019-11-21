#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import shutil
from io import StringIO
from os import getcwd as cwd
from os.path import basename, dirname, expanduser, isfile, join

import click

from future_lain_cli.utils import (CHART_DIR_NAME, FUTURE_CLUSTERS,
                                   HELM_WEIRD_STATE, TEMPLATE_DIR, KVPairType,
                                   Registry, apply_secret, deploy_toast,
                                   dump_secret, echo, edit_file, ensure_absent,
                                   ensure_initiated, error, example_lain_yaml,
                                   find, get_app_status, goodjob, helm,
                                   kubectl, legacy_lain, populate_helm_context,
                                   populate_helm_context_from_lain_yaml,
                                   tell_cluster, tell_cluster_info,
                                   tell_cluster_values_file,
                                   tell_helm_set_clause, tell_image_tag,
                                   tell_secret, template_env, yadu, yalo)


@click.group()
@click.pass_context
def lain(ctx):
    tell_cluster()
    try:
        populate_helm_context(ctx.obj)
    except FileNotFoundError:
        pass


@lain.command()
@click.option('--appname', default=basename(cwd()), help='Name of the app, default to the lain.yaml appname. But if --lain-yaml isn\'t provided, the dirname of cwd will be used')
@click.option('--lain-yaml', type=click.File(), default=lambda: StringIO(example_lain_yaml), help='Generate helm charts from the given lain.yaml, if not provided, an example chart will be generated')
@click.option('--force', '-f', is_flag=True, help=f'Remove ./{CHART_DIR_NAME} and then regenerate')
@click.pass_context
def init(ctx, appname, lain_yaml, force):
    # just using this command to ensure kubectl is downloaded
    kubectl('version', '--client=true', capture_output=True)
    ctx.obj['appname'] = appname
    populate_helm_context_from_lain_yaml(ctx.obj, lain_yaml)
    # appname could change later during populate_helm_context_from_lain_yaml
    appname = ctx.obj['appname']
    if force:
        ensure_absent(CHART_DIR_NAME)

    try:
        os.mkdir(CHART_DIR_NAME)
    except FileExistsError:
        err = f'''Cannot render helm chart because Directory ./{CHART_DIR_NAME} already exists.
        If you really wanna do this again, use the -f option'''
        error(err)
        ctx.exit(1)

    for f in find(TEMPLATE_DIR):
        render_dest = join(CHART_DIR_NAME, f.replace('.j2', '', 1))
        if f.endswith('.j2'):
            template = template_env.get_template(basename(f))
            with open(render_dest, 'w') as f:
                f.write(template.render(**ctx.obj))
        else:
            src = join(TEMPLATE_DIR, f)
            os.makedirs(dirname(render_dest), exist_ok=True)
            shutil.copyfile(src, render_dest)

    res = helm('lint', f'./{CHART_DIR_NAME}')
    if res.returncode:
        ctx.exit(res.returncode)

    toast = f'''A helm chart is generated under the ./{CHART_DIR_NAME} directory. What's next?

    * Review ./{CHART_DIR_NAME}/values.yaml
    * If this app needs secret files or env, you should create them:
        # add env to Kubernetes Secret
        lain env edit
        # add secret files to Kubernetes Secret
        lain use [CLUSTER]
        lain secret add [FILE]
    * If this app uses `[appname].lain` services, ack and substitute them with [appname]-web, provided they have already been deployed on lain4
    '''
    goodjob(toast)


@lain.command()
@click.argument('cluster', type=click.Choice(FUTURE_CLUSTERS))
@click.pass_context
def use(ctx, cluster):
    """link kubeconfig of specified CLUSTER to ~/.kube/config, so that you
    don\'t have to type --kubeconfig when using kubectl, or helm"""
    kubeconfig_file = f'~/.kube/kubeconfig-{cluster}'
    src = expanduser(kubeconfig_file)
    if not isfile(src):
        error(f'{kubeconfig_file} not found, go fetch it from 1pw, under the "kubeconfig" item', exit=1)

    dest = expanduser('~/.kube/config')
    ensure_absent(dest)
    os.symlink(src, dest)
    kubectl('config', 'set-context', '--current', '--namespace=default')
    cluster_info = tell_cluster_info()
    domain = cluster_info['legacy_lain_domain']
    legacy_lain('config', 'save', cluster, 'domain', domain)
    goodjob(f'You did good, next time you use lain4 / helm / kubectl, it\'ll point to cluster {cluster}')


@lain.command()
@click.argument('deployments', nargs=-1)
@click.option('--deduce', is_flag=True, help='use latest imageTag from registry rather than `lain meta`')
@click.pass_context
def update_image(ctx, deployments, deduce):
    """update, and only update image for some deploy"""
    choices = set(ctx.obj['values']['deployments'].keys())
    if not deployments:
        error(f'specify at least one deployment, choose from: {choices}', exit=1)

    deployments = set(deployments)
    if not deployments.issubset(choices):
        wrong_deployments = deployments.difference(choices)
        error(f'unknown deploy {wrong_deployments}, choose from: {choices}', exit=1)

    registry = Registry(tell_cluster_info()['registry'])
    appname = ctx.obj['appname']
    if deduce:
        recent_tags = registry.images_list(appname)
        if not recent_tags:
            error('wow, there\'s no pushed image at all', exit=1)

        image_tag = recent_tags[0]
    else:
        image_tag = tell_image_tag()

    image = registry.make_image(image_tag)
    for deploy in deployments:
        res = kubectl('set', 'image', f'deployment/{appname}-{deploy}', f'{deploy}={image}', '--all')
        if res.returncode:
            error('abort due to kubectl failure, if you don\'t understand the above error output, seek help from SA')


@lain.command()
@click.argument('whatever', nargs=-1)
@click.option('--set', 'pairs', multiple=True, type=KVPairType(), help='Override values in values.yaml, same as helm')
@click.pass_context
def deploy(ctx, whatever, pairs):
    """\b
    deploy your app.
    for lain4 clusters:
        lain use [CLUSTER]
        lain deploy
    for legacy clusters, your command will be passed to the legacy version of lain-cli
    """
    if whatever:
        cluster = whatever[0]
        if cluster in FUTURE_CLUSTERS:
            error('For lain4 clusters, just type `lain deploy`', exit=1)

        legacy_lain('deploy', *whatever, exit=True)

    # no big deal, just using this line to initialized env first
    # otherwise this deploy may fail because envFrom is referencing a
    # non-existent secret
    tell_secret(ctx.obj['env_name'])
    ensure_initiated(chart=True, secret=True)
    appname = ctx.obj['appname']
    status = get_app_status(appname)
    if status and status['info']['status'] in HELM_WEIRD_STATE:
        err = f'''Chart deployed but in a weird state. Now do this:
            helm status {appname}
            kubectl get po -l app.kubernetes.io/name={appname}
            kubectl describe pod [POD_NAME]
            kubectl logs -f pod [POD_NAME]
        Once you learn and fix the problem, delete this failed install VERY CAREFULLY:
            helm delete {appname}'''
        error(err)
        ctx.exit(1)

    headsup = f'''
    While being deployed, you can use kubectl to check the status of you app:
        kubectl get po -l app.kubernetes.io/name={appname}
        kubectl describe po [POD_NAME]
        kubectl logs -f [POD_NAME]
    '''
    echo(headsup)
    set_clause = tell_helm_set_clause(pairs)
    options = ['--atomic', '--install', '--wait', '--set', set_clause]
    # if chart/values-[CLUSTER].yaml exists, use it
    values_file = tell_cluster_values_file()
    if values_file:
        options.extend(['-f', values_file])

    res = helm('upgrade', *options, appname, f'./{CHART_DIR_NAME}')
    if res.returncode:
        ctx.exit(res.returncode)

    deploy_toast()


@lain.command()
@click.pass_context
def build(ctx):
    """\b
    legacy_lain functionality, if build clause exists in chart/values.yaml,
    then uses values.yaml as lain.yaml. otherwise this command behaves just
    like legacy_lain"""
    if 'build' not in ctx.obj['values']:
        fake_lain_yaml = False
    else:
        fake_lain_yaml = True

    legacy_lain('build', fake_lain_yaml=fake_lain_yaml)


@lain.command()
@click.argument('whatever', nargs=-1)
@click.pass_context
def tag(ctx, whatever):
    """legacy_lain functionality, for lain4 clusters, you don't need to
    manually tag"""
    legacy_lain('tag', *whatever)


@lain.command()
@click.argument('whatever', nargs=-1)
@click.pass_context
def push(ctx, whatever):
    """\b
    push app image using legacy_lain.
    For lain4 clusters, push target will automatically be detected:
        lain use [CLUSTER]
        lain push
    For legacy_lain:
        lain push [CLUSTER]
    """
    if not whatever:
        cluster = ctx.obj['cluster']
        res = legacy_lain('tag', cluster)
        if res.returncode:
            error(f'legacy_lain tag failed, maybe you need to lain use {cluster} one more time', exit=1)

        whatever = [cluster]

    legacy_lain('push', *whatever)


@lain.group()
@click.pass_context
def env(ctx):
    """\b
    env management.
    on lain4 clusters, env are managed by Kubernetes Secret, and referenced
    using envFrom in Kubernetes manifests.
    this cli merely exposes some handy editing functionalities.
    """


@env.command()
@click.argument('pairs', type=KVPairType(), nargs=-1)
@click.pass_context
def add(ctx, pairs):
    """\b
    env management.
        lain secret add FOO=BAR EGG=SPAM
    """
    if not pairs:
        goodjob('You just added nothing, what a great way to use this command', exit=True)

    env_dic = tell_secret(ctx.obj['env_name'], init='env')
    for k, v in pairs:
        env_dic['data'][k] = v

    apply_secret(env_dic)
    goodjob(f'env edited, you can use `lain env show` to view them', exit=True)


@env.command()
@click.pass_context
def show(ctx):
    """env management."""
    secret_dic = tell_secret(ctx.obj['env_name'], init='env')
    echo(yadu(secret_dic))


@env.command()
@click.pass_context
def edit(ctx):
    """env management."""
    f = dump_secret(ctx.obj['env_name'], init='env')
    edit_file(f)
    secret_dic = yalo(f)
    apply_secret(secret_dic)


@lain.group()
def secret():
    """\b
    secret file management.
    on lain4 clusters, secrets are managed by Kubernetes Secret, this cli
    merely exposes some handy editing functionalities.
    on lain2/3 clusters, secrets are managed by lvault, in order to bring
    backward compatibilities, the cli arguments are very weird, we'll remove
    them once lain2/3 became obsolete
    """


@secret.command()
@click.argument('whatever', nargs=-1)
@click.option('-f', help='The secret file to add, this is a legacy_lain option')
@click.pass_context
def add(ctx, whatever, f):
    """\b
    secretfile management.
    for lain4:
        lain secret add [FILE]
    for legacy_lain:
        lain secret add -f [FILE] [CLUSTER] [PROC] [PATH]

    lain4 uses the same set of secret files for all your application process,
    and mountpath has be defined in chart/values.yaml
    """
    if not whatever:
        goodjob('You just added nothing, what a great way to use this command', exit=True)
    if len(whatever) > 1:
        legacy_lain('secret', 'add', '-f', f, *whatever, exit=True)

    secret_name = ctx.obj['secret_name']
    f = whatever[0]
    fname = basename(f)
    secret_dic = tell_secret(secret_name, init='secret')
    secret_dic['data'][fname] = open(f).read()
    apply_secret(secret_dic)
    goodjob(f'{f} has been added to secret/{secret_name}, now you should delete this file', exit=True)


@secret.command()
@click.argument('whatever', nargs=-1)
@click.pass_context
def show(ctx, whatever):
    """\b
    secretfile management.
    for lain4:
        lain secret show
    for legacy_lain:
        legacy_lain secret show [CLUSTER] [PROC]

    lain4 uses the same set of secret files for all your application process,
    and mountpath has be defined in chart/values.yaml
    """
    if whatever:
        legacy_lain('secret', 'show', *whatever, exit=True)

    secret_dic = tell_secret(ctx.obj['secret_name'], init='secret')
    echo(yadu(secret_dic))
    ctx.exit(0)


@secret.command()
@click.pass_context
def edit(ctx):
    """secret management. For lain4 only."""
    f = dump_secret(ctx.obj['secret_name'], init='secret')
    edit_file(f)
    secret_dic = yalo(f)
    apply_secret(secret_dic)


def main():
    lain(obj={})


if __name__ == '__main__':
    main()
