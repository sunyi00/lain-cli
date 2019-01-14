# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import argh
import jinja2
from os.path import dirname, join, abspath
from jenkinsapi.jenkins import Jenkins

from lain_sdk.util import info, error, warn
from lain_cli.utils import TwoLevelCommandBase, lain_yaml


def render(tpl_path, context):
    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(path or './')
    ).get_template(filename).render(context)


def get_jenkins():
    return Jenkins('http://jenkins.in.ein.plus', username='sa', password='9ikqtL2YnMEzVP')


def gen_jobname(appname, phase, ci_type=None):
    if not ci_type or ci_type == 'brain':
        if phase == 'master':
            return appname
        elif phase == 'pr':
            return '{}-pr'.format(appname)
        elif phase == 'dev-deploy':
            return 'deployment-dev-{}'.format(appname)
        elif phase == 'pipeline':
            return 'pipeline-{}'.format(appname)
        else:
            raise "invalid job phase: {}".format(phase)
    elif ci_type == 'lib':
        if phase == 'master':
            return 'lib--{}'.format(appname)
        elif phase == 'pr':
            return 'lib--{}-pr'.format(appname)
        elif phase == 'packaging':
            return 'packaging--{}'.format(appname)
        else:
            raise "invalid job phase: {}".format(phase)
    elif ci_type == 'packaging':
        if phase == 'packaging':
            return 'packaging--{}'.format(appname)
        else:
            raise "invalid job phase: {}".format(phase)
    else:
        raise "invalid ci_type: {}".format(ci_type)


def create_job(appname, phase, ci_type, tmpl_dir=''):
    jobname = gen_jobname(appname, phase, ci_type=ci_type)
    repo = 'ein-plus/{}'.format(appname)
    if not tmpl_dir:
        tmpl_dir = join(dirname(abspath(__file__)), 'tmpl')

    typed_tmpl_file = os.path.join(
        tmpl_dir,
        '{}_{}.tmpl'.format(ci_type, phase)
    )

    if os.path.isfile(typed_tmpl_file):
        print('found typed tmpl file: {}'.format(typed_tmpl_file))
        tmpl_file = typed_tmpl_file
    else:
        print('tmpl missing for ci type: {}'.format(ci_type))
        return None
    job_config = render(tmpl_file, {'repo': repo, 'appname': appname})
    jenkins = get_jenkins()
    newjob = jenkins.create_job(jobname=jobname, xml=job_config)
    print(newjob)
    return newjob


def get_job(appname, phase, ci_type=''):
    jenkins = get_jenkins()
    jobname = gen_jobname(appname, phase, ci_type=ci_type)
    print('getting job: {}'.format(jobname))
    try:
        return jenkins[jobname]
    except:
        return None


def show_job_status(job):
    try:
        build = job.get_last_build()
        print(build.baseurl)
        print(build.get_description() or 'no description')
        if build.is_running():
            warn('{} : Running'.format(job.name))
        elif build.is_good():
            info('{} : Passed'.format(job.name))
        else:
            error('{} : Failed'.format(job.name))
    except:
        warn('{} : no build'.format(job.name))


class CiCommands(TwoLevelCommandBase):
    '''
    ci command
    '''

    @classmethod
    def subcommands(self):
        return [self.create, self.status]

    @classmethod
    def namespace(self):
        return "ci"

    @classmethod
    def help_message(self):
        return "ci operation: including create, status"

    @classmethod
    def status(cls):
        """
        show lain app ci job status
        """

        yml = lain_yaml(ignore_prepare=True)
        appname = yml.appname
        for phase in ['master', 'pr', 'dev-deploy', 'pipeline']:
            job = get_job(appname, phase)
            if job is not None:
                show_job_status(job)
            else:
                warn('no job: {} {}'.format(appname, phase))

    @classmethod
    @argh.arg('-d', '--tmpl-dir', default='')
    @argh.arg('-t', '--ci-type', default='app')
    @argh.arg('-n', '--appname', default='')
    def create(cls, appname='', ci_type='app', tmpl_dir=''):
        """
        create job
        """

        if not appname:
            yml = lain_yaml(ignore_prepare=True)
            appname = yml.appname
        if ci_type == 'lib':
            phase_list = ['master', 'pr', 'packaging']
        else:
            phase_list = ['master', 'pr', 'dev-deploy', 'pipeline']

        for phase in phase_list:
            job = get_job(appname, phase, ci_type)
            if job is not None:
                warn('job exists: {}'.format(job.baseurl))
            else:
                try:
                    newjob = create_job(appname, phase, ci_type, tmpl_dir=tmpl_dir)
                    if newjob is not None:
                        info('job created: {}'.format(newjob.baseurl))
                    else:
                        error('failed to create job with params: {} {} {} {}'.format(appname, phase, ci_type, tmpl_dir))
                except Exception as e:
                    error('failed to create job with params: {} {} {} {}'.format(appname, phase, ci_type, tmpl_dir))
                    error(str(e))
