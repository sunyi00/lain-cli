# -*- coding: utf-8 -*-
import json
import sys

import requests
from argh.decorators import arg

from lain_cli.auth import get_auth_header
from lain_cli.utils import (TwoLevelCommandBase, check_phase, get_domain,
                            lain_yaml, ClusterConfig, render_secret)
from lain_sdk.util import error, info


class SecretCommands(TwoLevelCommandBase):
    '''
    allow add secret files for app, lain will add the secret file into
    image of the proc when deploying.
    '''

    @classmethod
    def subcommands(self):
        return [self.show, self.add, self.delete]

    @classmethod
    def namespace(self):
        return "secret"

    @classmethod
    def help_message(self):
        return "secret operation: including add, delete or show secret files of the app"

    @classmethod
    @arg('phase', help="lain cluster phase id, can be added by lain config save")
    @arg('procname', help="proc name of the app")
    @arg('-l', '--lvault', help='lvault url')
    def show(cls, phase, procname, path=None, lvault=None):
        """
        show secret file of special procname in different phase

        path: absolute path of config file, eg : /lain/app/config
        """

        check_phase(phase)

        params = dict(name=phase)
        if lvault is not None:
            params['lvault'] = lvault

        cluster_config = ClusterConfig(**params)

        yml = lain_yaml(ignore_prepare=True)
        auth_header = get_auth_header('unknown')
        proc = yml.procs.get(procname, None)
        if proc is None:
            error('proc {} does not exist'.format(procname))
            exit(1)

        podgroup_name = "{}.{}.{}".format(yml.appname, proc.type.name, proc.name)
        lvault_url = "http://%s/v2/secrets?app=%s&proc=%s" % (
            cluster_config.lvault, yml.appname, podgroup_name)
        if path:
            lvault_url += "&path=%s" % path

        show_response = requests.get(lvault_url, headers=auth_header)
        if show_response.status_code < 300:
            info("secret file detail:")
            if sys.version_info.major == 2:
                print(json.dumps(show_response.json(), encoding="utf-8", ensure_ascii=False, indent=2))
            else:
                render_secret(show_response.json())
        else:
            error("shit happened : %s" % show_response.text)

    @classmethod
    @arg('phase', help="lain cluster phase id, can be added by lain config save")
    @arg('procname', help="proc name of the app")
    @arg('path', help='absolute path of config file, eg : /lain/app/config')
    @arg('-l', '--lvault', help='lvault url')
    def add(cls, phase, procname, path, content=None, file=None, lvault=None):
        """
        add secret file for different phase

        content: content of the secret file
        file: read secret content from a specify file
        """

        if file is None and content is None:
            error("need specify the content use -c or -f parameter")
            exit(1)

        if file is not None:
            try:
                f = open(file)
                content = f.read()
            except Exception as e:
                error("error read file %s : %s" % (file, str(e)))
                exit(1)

        check_phase(phase)
        yml = lain_yaml(ignore_prepare=True)

        params = dict(name=phase)
        if lvault is not None:
            params['lvault'] = lvault

        cluster_config = ClusterConfig(**params)

        auth_header = get_auth_header('unknown')
        proc = yml.procs.get(procname, None)
        if proc is None:
            error('proc {} does not exist'.format(procname))
            exit(1)

        podgroup_name = "{}.{}.{}".format(yml.appname, proc.type.name, proc.name)
        lvault_url = "http://%s/v2/secrets?app=%s&proc=%s&path=%s" % (
            cluster_config.lvault, yml.appname, podgroup_name, path)
        payload = {"content": content}

        add_response = requests.put(lvault_url, headers=auth_header, json=payload)
        if add_response.status_code < 300:
            info("add successfully.")
        else:
            error("shit happened : %s" % add_response.text)

    @classmethod
    @arg('phase', help="lain cluster phase id, can be added by lain config save")
    @arg('procname', help="proc name of the app")
    @arg('path', help='absolute path of config file, eg : /lain/app/config')
    @arg('-l', '--lvault', help='lvault url')
    def delete(cls, phase, procname, path, lvault=None):
        """
        delete secret file for different phase
        """

        check_phase(phase)
        yml = lain_yaml(ignore_prepare=True)

        params = dict(name=phase)
        if lvault is not None:
            params['lvault'] = lvault

        cluster_config = ClusterConfig(**params)

        auth_header = get_auth_header('unknown')
        proc = yml.procs.get(procname, None)
        if proc is None:
            error('proc {} does not exist'.format(procname))
            exit(1)

        podgroup_name = "{}.{}.{}".format(yml.appname, proc.type.name, proc.name)
        lvault_url = "http://%s/v2/secrets?app=%s&proc=%s&path=%s" % (
            cluster_config.lvault, yml.appname, podgroup_name, path)

        delete_response = requests.delete(lvault_url, headers=auth_header)
        if delete_response.status_code < 300:
            info("delete successfully.")
        else:
            error("shit happened : %s" % delete_response.text)
