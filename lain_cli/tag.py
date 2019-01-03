# -*- coding: utf-8 -*-
from argh.decorators import arg

import lain_sdk.mydocker as docker
from lain_cli.utils import check_phase, get_domain, lain_yaml, ClusterConfig
from lain_sdk.util import error, info


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-r', '--registry', help='registry url')
def tag(phase, registry=None):
    """
    Tag release and meta images
    """

    check_phase(phase)
    params = dict(name=phase)
    if registry is not None:
        params['registry'] = registry
    cluster_config = ClusterConfig(**params)
    info("Taging meta and relese image ...")
    yml = lain_yaml(ignore_prepare=True)
    meta_version = yml.meta_version
    if meta_version is None:
        error("please git commit.")
        return None
    meta_tag = "%s:meta-%s" % (yml.appname, meta_version)
    release_tag = "%s:release-%s" % (yml.appname, meta_version)
    phase_meta_tag = docker.gen_image_name(yml.appname, 'meta', meta_version, cluster_config.registry)
    phase_release_tag = docker.gen_image_name(yml.appname, 'release', meta_version, cluster_config.registry)
    meta_code = docker.tag(meta_tag, phase_meta_tag)
    release_code = docker.tag(release_tag, phase_release_tag)
    if meta_code or release_code:
        error("Error lain tag.")
    else:
        info("Done lain tag.")
