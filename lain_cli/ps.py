# coding: utf-8

import requests
from argh.decorators import arg

from lain_cli.auth import get_auth_header
from lain_cli.utils import (check_phase, get_domain, lain_yaml,
                            render_app_status, ClusterConfig)
from lain_sdk.util import error


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-o', '--output', choices=['pretty', 'json', 'json-pretty'], default='pretty')
@arg('-c', '--console', help='console url')
def ps(phase, output='pretty', console=None):
    """
    Show basic deploy messages of app
    """

    check_phase(phase)

    params = dict(name=phase)
    if console is not None:
        params['console'] = console

    cluster_config = ClusterConfig(**params)

    yml = lain_yaml(ignore_prepare=True)

    access_token = 'unknown'
    auth_header = get_auth_header(access_token)

    repo_url = "http://%s/api/v1/repos/%s/" % (cluster_config.console, yml.appname)
    repo_r = requests.get(repo_url, headers=auth_header)
    if repo_r.status_code == 404:
        error('app {} has not been reposited at {}'.format(
            yml.appname, phase
        ))
        exit(1)
    elif repo_r.status_code == 200:
        pass
    else:
        error("shit happend: %s" % repo_r.content)
        exit(1)

    app_url = "http://%s/api/v1/apps/%s/" % (cluster_config.console, yml.appname)
    app_r = requests.get(app_url, headers=auth_header)
    if app_r.status_code == 200:
        app_status = app_r.json()["app"]
        render_app_status(app_status, output)
    elif app_r.status_code == 404:
        error('app {} has not been deployed at {}'.format(
            yml.appname, phase
        ))
        exit(1)
    else:
        error("shit happend: %s" % repo_r.content)
        exit(1)
