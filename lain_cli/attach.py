# -*- coding: utf-8 -*-
from argh.decorators import arg

from entryclient import EntryClient
from lain_cli.utils import check_phase, get_domain, lain_yaml, ClusterConfig
from lain_sdk.util import error, info


@arg('phase', help="lain cluster phase id, can be added by lain config save")
@arg('-t', '--target', help='The target appname to attach, if not set, will be the appname of the working dir')
@arg('-e', '--entry', help='entry url')
def attach(phase, proc_name, instance_no, target=None, entry=None):
    """
    Attach the stdout/stderr of the container
    """

    check_phase(phase)
    yml = lain_yaml(ignore_prepare=True)

    params = dict(name=phase)
    if entry is not None:
        params['entry'] = entry

    cluster_config = ClusterConfig(**params)

    appname = target if target else yml.appname
    access_token = 'unknown'
    endpoint = "wss://%s/attach" % cluster_config.entry
    header_data = ["access-token: %s" % access_token,
                   "app-name: %s" % appname,
                   "proc-name: %s" % proc_name,
                   "instance-no: %s" % instance_no]
    try:
        client = EntryClient(endpoint, header=header_data)
        info("Start to attach the stdout/stderr of the container. Press <Ctrl+c> to stop...")
        client.attach_container()
    except KeyboardInterrupt:
        pass
    except Exception:
        error("Server stops the connection. Ask admin for help.")
