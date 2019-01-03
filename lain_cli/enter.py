# -*- coding: utf-8 -*-
import os

from argh.decorators import arg

from entryclient import EntryClient
from lain_cli.utils import check_phase, get_domain, lain_yaml, ClusterConfig
from lain_sdk.util import error


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-t', '--target', help='The target appname to enter. If it\'s not set, it will be the appname of the working dir')
@arg('-e', '--entry', help='entry url')
def enter(phase, proc_name, instance_no, target=None, entry=None):
    """
    Enter the container of specific proc
    """

    check_phase(phase)
    yml = lain_yaml(ignore_prepare=True)

    params = dict(name=phase)
    if entry is not None:
        params['entry'] = entry

    cluster_config = ClusterConfig(**params)

    appname = target if target else yml.appname
    access_token = 'unknown'

    term_type = os.environ.get("TERM", "xterm")
    endpoint = "wss://%s/enter" % cluster_config.entry
    header_data = ["access-token: %s" % access_token,
                   "app-name: %s" % appname,
                   "proc-name: %s" % proc_name,
                   "instance-no: %s" % instance_no,
                   "term-type: %s" % term_type]
    try:
        client = EntryClient(endpoint, header=header_data)
        client.invoke_shell()
    except Exception:
        error("Server stops the connection. Ask admin for help.")
