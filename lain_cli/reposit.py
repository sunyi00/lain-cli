# -*- coding: utf-8 -*-
from argh.decorators import arg

from lain_cli.auth import SSOAccess, authorize_and_check, get_auth_header
from lain_cli.utils import check_phase, get_domain, lain_yaml, reposit_app
from lain_sdk.util import info


@arg('phase', help="lain cluster phase id, can be added by lain config save")
def reposit(phase):
    """
    Initialize a repository in lain
    """

    check_phase(phase)
    info("Repositing ...")

    yml = lain_yaml(ignore_prepare=True)
    authorize_and_check(phase, yml.appname)

    access_token = SSOAccess.get_token(phase)
    auth_header = get_auth_header(access_token)

    console = "console.%s" % get_domain(phase)
    result = reposit_app(phase, yml.appname, console, auth_header)

    info("Done, %s" % result)
