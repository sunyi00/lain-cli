# -*- coding: utf-8 -*-
import requests
from argh.decorators import arg

from lain_cli.auth import get_auth_header
from lain_cli.utils import check_phase, get_domain, lain_yaml, ClusterConfig
from lain_sdk.util import error, info, warn


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-t', '--target', help='The target app to deploy, if not set, will be the appname of the working dir')
@arg('-p', '--proc', help='The proc wanted to undeploy')
@arg('-c', '--console', help='console url')
def undeploy(phase, target=None, proc=None, console=None):
    """
    Undeploy specific proc in the app or the whole app
    """

    check_phase(phase)

    params = dict(name=phase)
    if console is not None:
        params['console'] = console
    cluster_config = ClusterConfig(**params)

    yml = lain_yaml(ignore_prepare=True)
    appname = target if target else yml.appname

    access_token = 'unknown'
    auth_header = get_auth_header(access_token)
    if proc:
        undeploy_proc(proc, appname, cluster_config.console, auth_header)
    else:
        undeploy_app(appname, cluster_config.console, auth_header)


def undeploy_app(appname, console, auth_header):
    delete_url = "http://%s/api/v1/apps/%s/" % (console, appname)
    delete_r = requests.delete(delete_url, headers=auth_header)
    try:
        if delete_r.status_code == 202:
            info("delete app %s success." % appname)
            info("delete result details: ")
            print(delete_r.json()['msg'])
        else:
            warn("delete app %s fail: %s" % (appname, delete_r.json()['msg']))
    except Exception:
        error("shit happend: %s" % delete_r.content)
        exit(1)


def undeploy_proc(proc, appname, console, auth_header):
    proc_url = "http://%s/api/v1/apps/%s/procs/%s/" % (
        console, appname, proc
    )
    delete_r = requests.delete(proc_url, headers=auth_header)
    try:
        if delete_r.status_code == 202:
            info("delete proc %s success." % proc)
            info("delete result details: ")
            print(delete_r.json()['msg'])
        else:
            warn("delete proc %s fail: %s" % (proc, delete_r.json()['msg']))
    except Exception:
        error("shit happend: %s" % delete_r.content)
        exit(1)
