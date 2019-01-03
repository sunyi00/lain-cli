# -*- coding: utf-8 -*-
import sys

import lain_sdk.mydocker as docker
from argh.decorators import arg
from lain_sdk.util import error, info

from lain_cli.utils import check_phase, get_domain, lain_yaml, ClusterConfig


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-r', '--registry', help='registry url')
def push(phase, registry=None):
    """
    Push release and meta images
    """

    check_phase(phase)
    params = dict(name=phase)
    if registry is not None:
        params['registry'] = registry

    cluster_config = ClusterConfig(**params)
    info("Pushing meta and release images ...")
    yml = lain_yaml(ignore_prepare=True)
    meta_version = yml.meta_version
    if meta_version is None:
        error("please git commit.")
        return None

    phase_meta_tag = docker.gen_image_name(
        yml.appname, 'meta', meta_version, cluster_config.registry)
    phase_release_tag = docker.gen_image_name(
        yml.appname, 'release', meta_version, cluster_config.registry)
    meta_code = docker.push(phase_meta_tag)
    release_code = docker.push(phase_release_tag)
    if meta_code or release_code:
        error("Error lain push.")
        sys.exit(1)
