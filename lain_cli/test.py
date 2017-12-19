# -*- coding: utf-8 -*-
import sys
import time
from argh.decorators import arg
from lain_sdk.util import mkdir_p
from lain_sdk.mydocker import create, cp, remove_container
from lain_cli.utils import lain_yaml, info, error


def _keep_file(container_name, file):
    try:
        info('copied {} from test image...'.format(file))
        cp(container_name, file)
    except Exception:
        error('fail to copy {} from test image...'.format(file))


def _keep_files(image, files):
    container_name = 'tmp_{}'.format(int(time.time()))
    create(container_name, image)
    for f in files:
        _keep_file(container_name, f)
    remove_container(container_name, kill=False)


@arg('results', default=[], nargs='+', type=str)
def test(results):
    """
    Build test image and run test scripts defined in lain.yaml
    """

    passed, test_image = lain_yaml().build_test()
    if test_image and results:
        _keep_files(test_image, results)
    if not passed:
        sys.exit(1)
    else:
        sys.exit(0)
