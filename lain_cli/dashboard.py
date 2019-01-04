# -*- coding: utf-8 -*-
from operator import attrgetter

import requests
from argh.decorators import arg

from lain_cli.auth import get_auth_header
from lain_cli.utils import check_phase, get_app_state, get_domain, ClusterConfig
from lain_sdk.util import error, info


class AppInfo(object):
    """App info to show"""

    def __init__(self, app_info):
        self.appname = app_info.get("appname")
        self.metaversion = app_info.get("metaversion")
        self.state = get_app_state(app_info)

    @classmethod
    def new(cls, app_info):
        return AppInfo(app_info)


SORT_CHOICES = ['appname', 'metaversion', 'state']


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-s', '--sort', choices=SORT_CHOICES, help="sort type when displaying available apps")
@arg('-c', '--console', help='console url')
def dashboard(phase, sort='appname', console=None):
    """
    Basic dashboard of Lain
    """

    check_phase(phase)

    params = dict(name=phase)
    if console is not None:
        params['console'] = console

    cluster_config = ClusterConfig(**params)

    print_welecome()
    print_workflows()
    access_token = 'unknown'
    auth_header = get_auth_header(access_token)

    print_available_repos(cluster_config.console, auth_header)
    print_available_apps(cluster_config.console, auth_header, sort)


def print_welecome():
    info('##############################')
    info('#      Welcome to Lain!      #')
    info('##############################')


def print_workflows():
    info('Below is the recommended workflows :')
    info('  lain reposit => lain prepare => lain build => lain tag => lain push => lain deploy')


def render_repos(repos):
    repos.sort()
    for repo in repos:
        print("{}  ".format(repo)),


def render_apps(apps, sort_type):
    apps.sort(key=attrgetter(sort_type))
    for app in apps:
        print("{:<30}  {:<60}  {:<10}".format(
            app.appname, app.metaversion, app.state))


def print_available_repos(console, auth_header):
    repos_url = "http://%s/api/v1/repos/" % console
    repos_res = requests.get(repos_url, headers=auth_header)
    info('Available repos are :')
    if repos_res.status_code == 200:
        repos = repos_res.json()["repos"]
        render_repos([repo["appname"] for repo in repos])
        print('')
    else:
        error("shit happened : %s" % repos_res.content)


def print_available_apps(console, auth_header, sort_type):
    apps_url = "http://%s/api/v1/apps/" % console
    apps_res = requests.get(apps_url, headers=auth_header)
    info('Available apps are :')
    print("{:<30}  {:<60}  {:<10}".format(
        "Appname", "MetaVersion", "State"))
    if apps_res.status_code == 200:
        apps = apps_res.json()["apps"]
        render_apps([AppInfo.new(app) for app in apps], sort_type)
    else:
        error("shit happened: %s" % apps_res.content)

