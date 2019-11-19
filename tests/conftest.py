from os import chdir
import sys
from os.path import abspath, dirname, join

import pytest

from future_lain_cli.utils import CHART_DIR_NAME, ensure_absent, helm

TESTS_BASE_DIR = dirname(abspath(__file__))
DUMMY_APPNAME = 'dummy'
DUMMY_REPO = f'tests/{DUMMY_APPNAME}'
DUMMY_IMAGE_TAG = 'release-1574173182-762b7a951e2059543203a7815ca96757527b4161'
TEST_CLUSTER = 'bei'
DUMMY_URL = f'http://{DUMMY_APPNAME}.{TEST_CLUSTER}.ein.plus'


@pytest.fixture(scope='session')
def dummy(request):

    def tear_down():
        ensure_absent(join(DUMMY_REPO, CHART_DIR_NAME))
        helm('delete', DUMMY_APPNAME)

    tear_down()
    sys.path.append(TESTS_BASE_DIR)
    chdir(DUMMY_REPO)
    request.addfinalizer(tear_down)
