from concurrent.futures import ThreadPoolExecutor
from functools import partial

import requests
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout

from future_lain_cli.utils import context, ensure_str, kubectl, template_env


def kube_text():
    ctx = context()
    appname = ctx.obj['appname']
    res = kubectl('get', 'po', '-o=wide', '--field-selector=status.phase!=Succeeded', '-l', f'app.kubernetes.io/name={appname}', capture_output=True)
    return ensure_str(res.stdout)


def test_url(url):
    try:
        res = requests.get(url, timeout=1)
    except Exception as e:
        return str(e)
    return res


ingress_text_str = '''{%- for res in results %}
{{ res.request.url }}   {{ res.status_code }}   {{ res.text | brief }}
{%- endfor %}
'''
ingress_text_template = template_env.from_string(ingress_text_str)


def ingress_text():
    ctx = context()
    urls = ctx.obj['urls']
    rl = []
    # why use ThreadPoolExecutor?
    # because we can't use loop.run_until_complete in the main thread
    # and why is that?
    # because prompt_toolkit application itself runs in a asyncio eventloop
    # you can't tell the current eventloop to run something for you if the
    # invoker itself lives in that eventloop
    # ref: https://bugs.python.org/issue22239
    with ThreadPoolExecutor(max_workers=len(urls)) as e:
        for url in urls:
            rl.append(e.submit(test_url, url))

    render_ctx = {'results': [future.result() for future in rl]}
    res = ingress_text_template.render(**render_ctx)
    return res


# prompt_toolkit window without cursor"""
Win = partial(Window, always_hide_cursor=True)
Title = partial(FormattedTextControl, style='fg:GreenYellow')


def build(refresh_interval=2):
    ctx = context()
    appname = ctx.obj['appname']
    # building kube container
    kube_text_control = FormattedTextControl(text=kube_text)
    kube_window = Win(content=kube_text_control)
    kube_container = HSplit([
        Win(
            height=1,
            content=Title(f'kubectl get po -o=wide --field-selector=status.phase!=Succeeded -l app.kubernetes.io/name={appname}'),
        ),
        kube_window,
    ])
    parts = [kube_container]
    # building ingress container
    if ctx.obj['urls']:
        ingress_text_control = FormattedTextControl(text=ingress_text)
        ingress_window = Win(content=ingress_text_control, always_hide_cursor=True)
        ingress_container = HSplit([
            Win(height=1, content=Title(f'url requests')),
            ingress_window,
        ])
        parts.append(ingress_container)

    # building root container
    root_container = HSplit(parts)
    kb = KeyBindings()

    @kb.add('c-c', eager=True)
    @kb.add('c-q', eager=True)
    def _(event):
        event.app.exit()

    app = Application(
        refresh_interval=refresh_interval,
        key_bindings=kb,
        layout=Layout(root_container),
        full_screen=True,
    )
    return app


def display_app_status():
    prompt_app = build()
    prompt_app.run()
