from tempfile import NamedTemporaryFile

from future_lain_cli.utils import yadu, yalo


def test_ya():
    dic = {'slogan': '人民有信仰民族有希望国家有力量'}
    f = NamedTemporaryFile()
    yadu(dic, f)
    f.seek(0)
    assert yalo(f) == dic
