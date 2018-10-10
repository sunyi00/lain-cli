import lain_sdk.mydocker as docker
from argh.decorators import arg

from lain_cli.auth import SSOAccess, get_auth_header
from lain_cli.utils import check_phase, get_domain


@arg('src_phase', help='The source registry domain for sync from, can not be None')
@arg('dst_phase', help="lain cluster phase id, can be added by lain config save")
@arg('appname', help="app name")
@arg('meta_version', help='The Meta version of some build')
def sync(src_phase, dst_phase, appname, meta_version):
    check_phase(src_phase)
    check_phase(dst_phase)

    src_domain = get_domain(src_phase)
    dst_domain = get_domain(dst_phase)

    src_registry = "registry.{domain}".format(domain=src_domain)
    dst_registry = "registry.{domain}".format(domain=dst_domain)

    src_phase_meta_tag = docker.gen_image_name(
        appname, 'meta', meta_version, src_registry)
    src_phase_release_tag = docker.gen_image_name(
        appname, 'release', meta_version, src_registry)

    dst_phase_meta_tag = docker.gen_image_name(
        appname, 'meta', meta_version, dst_registry)
    dst_phase_release_tag = docker.gen_image_name(
        appname, 'release', meta_version, dst_registry)

    if transfer_to(src_phase_meta_tag, dst_phase_meta_tag) != 0:
        return
    if transfer_to(src_phase_release_tag, dst_phase_release_tag) != 0:
        return

    access_token = SSOAccess.get_token(dst_phase)
    auth_header = get_auth_header(access_token)


def transfer_to(src_tag, dst_tag):
    if docker.pull(src_tag) != 0 or docker.tag(src_tag, dst_tag) != 0 or docker.push(dst_tag) != 0:
        return 1
    return 0
