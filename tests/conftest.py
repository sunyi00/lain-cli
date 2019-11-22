import sys
from os import chdir
from os.path import abspath, dirname, join

import pytest
from click.testing import CliRunner

from future_lain_cli.lain import lain
from future_lain_cli.utils import (CHART_DIR_NAME, ensure_absent, error, helm, Registry, FUTURE_CLUSTERS,
                                   kubectl)

TESTS_BASE_DIR = dirname(abspath(__file__))
DUMMY_APPNAME = 'dummy'
DUMMY_REPO = f'tests/{DUMMY_APPNAME}'
# dummy also has a :latest tag, see dummy/Makefile
DUMMY_IMAGE_TAG = 'release-1574411941-f4fca3bd2bf90691491c2280ef399f5dfa3b4daa'
TEST_CLUSTER = 'bei'
DUMMY_URL = f'http://{DUMMY_APPNAME}.{TEST_CLUSTER}.ein.plus'
# this url will point to proc.web-dev in example_lain_yaml
DUMMY_DEV_URL = f'http://{DUMMY_APPNAME}-dev.{TEST_CLUSTER}.ein.plus'


def tell_deployed_images(appname):
    res = kubectl('get', 'po', '-ojsonpath={..image}', '-l', f'app.kubernetes.io/name={appname}', capture_output=True)
    if res.returncode:
        error(res.stdout, exit=1)

    images = set(res.stdout.decode('utf-8').split(' "'))
    return images


def run(*args, returncode=0, **kwargs):
    runner = CliRunner()
    res = runner.invoke(*args, obj={}, **kwargs)
    assert res.exit_code == returncode
    return res


@pytest.fixture(scope='session')
def dummy(request):

    def tear_down():
        run(lain, args=['use', TEST_CLUSTER])
        ensure_absent(join(DUMMY_REPO, CHART_DIR_NAME))
        helm('delete', DUMMY_APPNAME)
        kubectl('delete', 'secret', f'{DUMMY_APPNAME}-env', f'{DUMMY_APPNAME}-secret')

    tear_down()
    sys.path.append(TESTS_BASE_DIR)
    chdir(DUMMY_REPO)
    request.addfinalizer(tear_down)


@pytest.fixture
def registry(request):
    cluster_info = FUTURE_CLUSTERS[TEST_CLUSTER]
    return Registry(cluster_info['registry'])
