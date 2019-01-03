# -*- coding: utf-8 -*-
from argh.decorators import arg

from lain_cli.auth import get_auth_header
from lain_cli.utils import check_phase, get_domain, lain_yaml, reposit_app, ClusterConfig
from lain_sdk.util import info


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-c', '--console', help='console url')
def reposit(phase, console=None):
    """
    Initialize a repository in lain
    """

    check_phase(phase)

    params = dict(name=phase)
    if console is not None:
        params['console'] = console

    cluster_config = ClusterConfig(**params)

    info("Repositing ...")

    yml = lain_yaml(ignore_prepare=True)

    access_token = 'unknown'
    auth_header = get_auth_header(access_token)

    result = reposit_app(phase, yml.appname, cluster_config.console, auth_header)

    info("Done, %s" % result)
