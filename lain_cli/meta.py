# -*- coding: utf-8 -*-
from lain_sdk.util import error, info
from lain_cli.utils import lain_yaml


def meta():
    """
    Show current meta version
    """

    meta_version = lain_yaml(ignore_prepare=True).repo_meta_version()
    if meta_version is None:
        error("please git commit.")
    else:
        print(lain_yaml(ignore_prepare=True).repo_meta_version())
