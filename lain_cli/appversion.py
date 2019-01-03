# -*- coding: utf-8 -*-
from argh.decorators import arg

from lain_sdk.util import warn, info
from lain_cli.utils import get_version_lists, lain_yaml, check_phase, ClusterConfig


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-r', '--registry', help='registry url')
def appversion(phase, registry=None):
    """
    Show available app versions in remote registry of lain
    """

    check_phase(phase)

    params = dict(name=phase)
    if registry is not None:
        params['registry'] = registry

    cluster_config = ClusterConfig(**params)

    yml = lain_yaml(ignore_prepare=True)

    version_list = get_version_lists(phase, yml.appname, ClusterConfig=cluster_config)
    print_available_version(version_list)


def print_available_version(version_list):
    if len(version_list) == 0:
        warn("No available release versions.")
    else:
        info("Below are the available versions: ")
        for version in version_list:
            print(version)
