from tempfile import NamedTemporaryFile

from future_lain_cli.utils import subprocess_run, tell_cluster, yadu, yalo
from tests.conftest import TEST_CLUSTER, run_under_click_context

BULLSHIT = '人民有信仰民族有希望国家有力量'


def test_ya():
    dic = {'slogan': BULLSHIT}
    f = NamedTemporaryFile()
    yadu(dic, f)
    f.seek(0)
    assert yalo(f) == dic


def test_subprocess_run(dummy):
    cmd = ['helm', 'version', '--bad-flag']
    cmd_result, func_result = run_under_click_context(
        subprocess_run,
        args=[cmd],
        kwargs={'check': True, 'capture_output': True},
    )
    # sensible output in stderr, rather than python traceback
    assert 'unknown flag: --bad-flag' in cmd_result.output


def test_tell_cluster(dummy):
    cmd_result, func_result = run_under_click_context(tell_cluster)
    assert func_result == TEST_CLUSTER

