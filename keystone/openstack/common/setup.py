# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Utilities with minimum-depends for use in setup.py
"""

import os
import re
import subprocess


def parse_mailmap(mailmap='.mailmap'):
    mapping = {}
    if os.path.exists(mailmap):
        fp = open(mailmap, 'r')
        for l in fp:
            l = l.strip()
            if not l.startswith('#') and ' ' in l:
                canonical_email, alias = [x for x in l.split(' ')
                                         if x.startswith('<')]
                mapping[alias] = canonical_email
    return mapping


def canonicalize_emails(changelog, mapping):
    """Takes in a string and an email alias mapping and replaces all
       instances of the aliases in the string with their real email.
    """
    for alias, email in mapping.iteritems():
        changelog = changelog.replace(alias, email)
    return changelog


# Get requirements from the first file that exists
def get_reqs_from_files(requirements_files):
    for requirements_file in requirements_files:
        if os.path.exists(requirements_file):
            return open(requirements_file, 'r').read().split('\n')
    return []


def parse_requirements(requirements_files=['requirements.txt',
                                           'tools/pip-requires']):
    requirements = []
    for line in get_reqs_from_files(requirements_files):
        if re.match(r'\s*-e\s+', line):
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1',
                                line))
        elif re.match(r'\s*-f\s+', line):
            pass
        else:
            requirements.append(line)

    return requirements


def parse_dependency_links(requirements_files=['requirements.txt',
                                               'tools/pip-requires']):
    dependency_links = []
    for line in get_reqs_from_files(requirements_files):
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))
    return dependency_links


def write_requirements():
    venv = os.environ.get('VIRTUAL_ENV', None)
    if venv is not None:
        with open("requirements.txt", "w") as req_file:
            output = subprocess.Popen(["pip", "-E", venv, "freeze", "-l"],
                                      stdout=subprocess.PIPE)
            requirements = output.communicate()[0].strip()
            req_file.write(requirements)


def _run_shell_command(cmd):
    output = subprocess.Popen(["/bin/sh", "-c", cmd],
                              stdout=subprocess.PIPE)
    return output.communicate()[0].strip()


def write_vcsversion(location):
    """Produce a vcsversion dict that mimics the old one produced by bzr.
    """
    if os.path.isdir('.git'):
        branch_nick_cmd = 'git branch | grep -Ei "\* (.*)" | cut -f2 -d" "'
        branch_nick = _run_shell_command(branch_nick_cmd)
        revid_cmd = "git rev-parse HEAD"
        revid = _run_shell_command(revid_cmd).split()[0]
        revno_cmd = "git log --oneline | wc -l"
        revno = _run_shell_command(revno_cmd)
        with open(location, 'w') as version_file:
            version_file.write("""
# This file is automatically generated by setup.py, So don't edit it. :)
version_info = {
    'branch_nick': '%s',
    'revision_id': '%s',
    'revno': %s
}
""" % (branch_nick, revid, revno))


def write_git_changelog():
    """Write a changelog based on the git changelog."""
    if os.path.isdir('.git'):
        git_log_cmd = 'git log --stat'
        changelog = _run_shell_command(git_log_cmd)
        mailmap = parse_mailmap()
        with open("ChangeLog", "w") as changelog_file:
            changelog_file.write(canonicalize_emails(changelog, mailmap))


def generate_authors():
    """Create AUTHORS file using git commits."""
    jenkins_email = 'jenkins@review.openstack.org'
    old_authors = 'AUTHORS.in'
    new_authors = 'AUTHORS'
    if os.path.isdir('.git'):
        # don't include jenkins email address in AUTHORS file
        git_log_cmd = "git log --format='%aN <%aE>' | sort -u | " \
                      "grep -v " + jenkins_email
        changelog = _run_shell_command(git_log_cmd)
        mailmap = parse_mailmap()
        with open(new_authors, 'w') as new_authors_fh:
            new_authors_fh.write(canonicalize_emails(changelog, mailmap))
            if os.path.exists(old_authors):
                with open(old_authors, "r") as old_authors_fh:
                    new_authors_fh.write('\n' + old_authors_fh.read())
