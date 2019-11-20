import sys
from os import chdir
from os.path import abspath, dirname, join

import pytest
from click.testing import CliRunner

from future_lain_cli.lain import lain
from future_lain_cli.utils import CHART_DIR_NAME, ensure_absent, helm

TESTS_BASE_DIR = dirname(abspath(__file__))
DUMMY_APPNAME = 'dummy'
DUMMY_REPO = f'tests/{DUMMY_APPNAME}'
DUMMY_IMAGE_TAG = 'release-1574173182-762b7a951e2059543203a7815ca96757527b4161'
TEST_CLUSTER = 'bei'
DUMMY_URL = f'http://{DUMMY_APPNAME}.{TEST_CLUSTER}.ein.plus'
# this url will point to proc.web-dev in example_lain_yaml
DUMMY_DEV_URL = f'http://{DUMMY_APPNAME}-dev.{TEST_CLUSTER}.ein.plus'


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

    tear_down()
    sys.path.append(TESTS_BASE_DIR)
    chdir(DUMMY_REPO)
    request.addfinalizer(tear_down)
