from click.testing import CliRunner
from time import sleep
import requests
from tenacity import retry, wait_fixed, stop_after_attempt

from future_lain_cli.lain import lain
from future_lain_cli.utils import kubectl
from tests.conftest import DUMMY_IMAGE_TAG, TEST_CLUSTER, DUMMY_URL


def test_workflow(dummy):
    runner = CliRunner()
    obj = {}

    def run(*args, returncode=0, **kwargs):
        res = runner.invoke(*args, obj=obj, **kwargs)
        assert res.exit_code == returncode
        return res

    # test lain init
    run(lain, args=['init'])
    # lain init should failed when chart directory already exists
    run(lain, args=['init'], returncode=1)
    # use -f to remove chart directory and redo
    run(lain, args=['init', '-f'])
    # lain use will switch current context switch to [TEST_CLUSTER]
    run(lain, args=['use', TEST_CLUSTER])
    # `lain secret show` will create a dummy secret
    run(lain, args=['secret', 'show'])
    # try to lain deploy using a bad image tag
    run(lain, args=['deploy', '--set', 'imageTag=noway'], returncode=1)
    # use a built image to deploy
    run(lain, args=['deploy', '--set', f'imageTag={DUMMY_IMAGE_TAG}'])
    # check service is up
    dummy_env = get_dummy_env()
    assert dummy_env['env']['FOO'] == 'BAR'
    assert dummy_env['secretfile'] == 'I\nAM\nBATMAN'


@retry(wait=wait_fixed(1), stop=stop_after_attempt(3))
def get_dummy_env():
    res = requests.get(DUMMY_URL)
    res.raise_for_status()
    return res.json()
