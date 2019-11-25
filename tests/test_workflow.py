from os.path import join

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from future_lain_cli.lain import lain
from future_lain_cli.utils import context, kubectl, legacy_lain, yadu, yalo
from tests.conftest import (CHART_DIR_NAME, DUMMY_APPNAME, DUMMY_DEV_URL,
                            DUMMY_IMAGE_TAG, DUMMY_URL, TEST_CLUSTER, run,
                            run_under_click_context, tell_deployed_images,
                            tell_pod_deploy_name)


def test_workflow(dummy, registry):
    # lain init should failed when chart directory already exists
    run(lain, args=['init'], returncode=1)
    # use -f to remove chart directory and redo
    run(lain, args=['init', '-f'])
    # lain use will switch current context switch to [TEST_CLUSTER]
    run(lain, args=['use', TEST_CLUSTER])
    # build and push to registry
    run(lain, args=['build'])
    run(lain, args=['push'])
    # see if this image is actually present on registry
    recent_tags = registry.tags_list(DUMMY_APPNAME)
    latest_tag = recent_tags[0]
    image_tag = legacy_lain('meta', capture_output=True).stdout.decode('utf-8').strip()
    assert image_tag and latest_tag.endswith(image_tag)
    # `lain secret show` will create a dummy secret
    run(lain, args=['secret', 'show'])
    # try to lain deploy using a bad image tag
    run(lain, args=['deploy', '--set', 'imageTag=noway'], returncode=1)
    # use a built image to deploy
    run(lain, args=['deploy', '--set', f'imageTag={latest_tag}'])
    # check service is up
    dummy_env = url_get_json(DUMMY_URL)
    assert dummy_env['env']['FOO'] == 'BAR'
    assert dummy_env['secretfile'] == 'I\nAM\nBATMAN'
    # check if hostAliases is working
    assert 'ein-es-m1' in dummy_env['hosts']
    # check imageTag is correct
    deployed_images = tell_deployed_images(DUMMY_APPNAME)
    assert len(deployed_images) == 1
    assert latest_tag in deployed_images.pop()
    # add one extra ingress rule to values.yaml
    values_path = join(CHART_DIR_NAME, 'values.yaml')
    with open(values_path) as f:
        values = yalo(f)

    values['ingresses'].append({
        'host': f'{DUMMY_APPNAME}-dev',
        'deployName': 'web-dev',
        'paths': ['/'],
    })
    yadu(values, values_path)
    overrideReplicaCount = 3
    overrideImageTag = 'latest'
    # add another env
    run(lain, args=['env', 'add', 'SCALE=BANANA'])
    # adjust replicaCount and imageTag in override values file
    override_values = {
        'deployments': {
            'web-dev': {
                'replicaCount': overrideReplicaCount,
                'imageTag': overrideImageTag,
            },
        },
        # this is just used to ensure helm template rendering
        'ingressAnnotations': {
            'nginx.ingress.kubernetes.io/proxy-next-upstream-timeout': 1,
        },
        'externalIngresses': [
            {'host': 'dummy-public.foo.cn', 'deployName': 'web', 'paths': ['/']},
            {'host': 'dummy-public.bar.cn', 'deployName': 'web', 'paths': ['/']},
        ],
    }
    yadu(override_values, f'{CHART_DIR_NAME}/values-{TEST_CLUSTER}.yaml')

    def get_helm_values():
        ctx = context()
        helm_values = ctx.obj['values']
        return helm_values

    # check if values-bei.yaml currectly overrides helm context
    cmd_result, helm_values = run_under_click_context(get_helm_values)
    assert helm_values['deployments']['web-dev']['replicaCount'] == overrideReplicaCount
    # this value is the same as before, in example_lain_yaml
    assert helm_values['deployments']['web-dev']['containerPort'] == 5000

    # deploy again to create newly added ingress rule
    run(lain, args=['deploy', '--set', f'imageTag={DUMMY_IMAGE_TAG}'])
    # check if the new ingress rule is created
    res = kubectl('get', 'ing', '-l', f'app.kubernetes.io/name={DUMMY_APPNAME}', '-o=jsonpath={..name}', capture_output=True)
    assert not res.returncode
    assert set(res.stdout.decode('utf-8').split()) == {
        'dummy-bei-ein-plus',
        'dummy-public-foo-cn',
        'dummy-dev-bei-ein-plus',
        'dummy-public-bar-cn',
    }
    # check pod name match its corresponding deploy name
    dummy_env = url_get_json(DUMMY_URL)
    assert tell_pod_deploy_name(dummy_env['env']['HOSTNAME']) == f'{DUMMY_APPNAME}-web'
    dummy_dev_env = url_get_json(DUMMY_DEV_URL)
    assert tell_pod_deploy_name(dummy_dev_env['env']['HOSTNAME']) == f'{DUMMY_APPNAME}-web-dev'
    # env is overriden in dummy-dev, see example_lain_yaml
    assert dummy_dev_env['env']['FOO'] == 'SPAM'
    assert dummy_dev_env['env']['SCALE'] == 'BANANA'
    # check if replicaCount is correctly overriden
    res = kubectl('get', 'deploy', f'{DUMMY_APPNAME}-web-dev', '-o=jsonpath={.spec.replicas}', capture_output=True)
    assert res.stdout.decode('utf-8').strip() == str(overrideReplicaCount)
    # check if imageTag is correctly overriden
    res = kubectl('get', 'deploy', f'{DUMMY_APPNAME}-web', '-o=jsonpath={.spec.template.spec..image}', capture_output=True)
    assert res.stdout.decode('utf-8').strip().endswith(DUMMY_IMAGE_TAG)
    res = kubectl('get', 'deploy', f'{DUMMY_APPNAME}-web-dev', '-o=jsonpath={.spec.template.spec..image}', capture_output=True)
    assert res.stdout.decode('utf-8').strip().endswith(overrideImageTag)
    # rollback imageTag for web-dev using `lain update_image`
    run(lain, args=['update-image', 'web-dev'])


@retry(wait=wait_fixed(1), stop=stop_after_attempt(3))
def url_get_json(url):
    res = requests.get(url)
    res.raise_for_status()
    return res.json()
