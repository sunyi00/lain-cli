# -*- coding: utf-8 -*-
import sys
from argh.decorators import arg
from lain_sdk.mydocker import copy_files_from_image
from lain_cli.utils import lain_yaml, info, error


@arg('-r', '--results', nargs='*', type=str)
def test(results=[]):
    """
    Build test image and run test scripts defined in lain.yaml
    """

    passed, test_image = lain_yaml().build_test()
    if test_image and results:
        copy_files_from_image(test_image, results)
    if not passed:
        sys.exit(1)
    else:
        sys.exit(0)
