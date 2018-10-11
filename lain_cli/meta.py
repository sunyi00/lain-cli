# -*- coding: utf-8 -*-
from lain_cli.utils import lain_yaml
from lain_sdk.util import error


def meta():
    """
    Show current meta version
    """

    meta_version = lain_yaml(ignore_prepare=True).meta_version
    if meta_version is None:
        error("please git commit.")
    else:
        print(lain_yaml(ignore_prepare=True).meta_version())
