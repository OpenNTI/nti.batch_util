import os
import re
import csv
import sys
import codecs
import shutil
import argparse
import fileinput

from git import Repo
from git import Git


def parse_args():
    arg_parser = argparse.ArgumentParser(description="Creating child sites")
    arg_parser.add_argument('branch',
                            help="Branch's name")
    arg_parser.add_argument('-c', '--client',
                            help="Client's name",
                            default="opsrc")
    arg_parser.add_argument('-u', '--url',
                            help="Git url (ssh)",
                            default="git@github.com:NextThought/nti.app.sites.opsrc.git")
    arg_parser.add_argument('-td', '--tempdir',
                            help="Temporary directory",
                            required=True)
    arg_parser.add_argument('-ts', '--templatesite',
                            help="Template site",
                            default="chisholm")
    arg_parser.add_argument('-tsn', '--templatesitename',
                            help="Template site name",
                            default="Chisholm")
    arg_parser.add_argument('-base', '--basebranch',
                            default='master',
                            help="Base branch")
    return arg_parser.parse_args()


def clone_repo(client, git_url, tempdir, branch_name, base='master'):
    """
    clone repo nti.app.sites.clientname
    for example:
    client = 'ifsta'
    git_url = 'git@github.com:NextThought/nti.app.sites.ifsta.git'
    """
    project_name = 'nti.app.sites.{}'.format(client)
    repo = Repo.clone_from(git_url, os.path.join(tempdir, project_name), branch=base)
    new_branch = repo.create_head(branch_name)
    repo.head.set_reference(new_branch)
    return repo


def copy_template_child(child_sites_dir, client, template_site, child_names=()):
    children = {}
    if child_names:
        for name in child_names:
            template = '{}/{}_{}'.format(child_sites_dir, client, template_site)
            new_child = '{}/{}_{}'.format(child_sites_dir, client, name)
            shutil.copytree(template, new_child)
            children[name] = new_child
    return children


def process_new_child_sites(child_sites, child_sites_dir, client, templatesite, child_site_names, templatesitename):
    for child in child_sites:
        if child in child_site_names:
            new_site = child
            update_main_child_configure(child_sites_dir, client, templatesite, new_site)
            update_child_configure(child_sites[new_site], templatesite, new_site)
            update_child_sites(child_sites[new_site], templatesite, new_site)
            update_child_policy(child_sites[new_site], templatesite, new_site, templatesitename, child_site_names[new_site], )


def update_child_policy(child_dir, templatesite, new_site, templatesitename, new_site_name):
    filename = '{}/policy.py'.format(child_dir)
    replace_line(filename, templatesite, new_site)
    replace_line(filename, templatesitename, new_site_name)


def update_child_sites(child_dir, templatesite, new_site):
    filename = '{}/sites.py'.format(child_dir)
    replace_line(filename, templatesite, new_site)


def update_child_configure(child_dir, templatesite, new_site):
    filename = '{}/configure.zcml'.format(child_dir)
    replace_line(filename, templatesite, new_site)


def update_main_child_configure(child_sites_dir, client, templatesite, new_site):
    filename = '{}/configure.zcml'.format(child_sites_dir)
    org_str = '<include package=".{}_{}" />'.format(client, templatesite)
    add_str = '<include package=".{}_{}" />'.format(client, new_site)
    add_line_into_file(filename, templatesite, new_site)


def replace_line(file, searchExp, replaceExp):
    for line in fileinput.input(file, inplace=1):
        if searchExp in line:
            line = line.replace(searchExp, replaceExp)
        sys.stdout.write(line)


def add_line_into_file(file, searchExp, replaceExp):
    for line in fileinput.input(file, inplace=1):
        if searchExp in line:
            new_line = line.replace(searchExp, replaceExp)
            new_line = line + new_line
            line = line.replace(line, new_line)
        sys.stdout.write(line)


def read_csv(filename):
    """
    The CSV should consist of 'Client' and 'Client Name' header
    output looks something like: {'ifstatwo': 'IFSTA Two', 'ifstaone': 'IFSTA One', 'ifstathree': 'IFSTA Three'}
    """
    child_site_names = {}
    with open(filename, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            child_site_names[row['Client']] = row['Client Name']
    return child_site_names


def git_add_commit_push(repo, branch_name):
    repo.git.add(A=True)
    repo.git.commit(m='Adding child sites')
    repo.git.push("origin", branch_name)


def main():
    args = parse_args()

    child_sites_file = '{}/sites.csv'.format(args.tempdir)
    child_site_names = read_csv(child_sites_file)

    repo = clone_repo(args.client, args.url, args.tempdir, args.branch, args.basebranch)
    rw_dir = repo.working_dir

    child_sites_dir = '{}/src/nti/app/sites/{}/child_sites'.format(rw_dir, args.client)
    child_sites = copy_template_child(child_sites_dir, args.client, args.templatesite, child_names=child_site_names.keys())

    if child_sites:
        process_new_child_sites(child_sites, child_sites_dir, args.client,
                                args.templatesite, child_site_names, args.templatesitename)

    # we can run the following line from terminal using git command if we want to check thing first before pushing the change
    # git_add_commit_push(repo, args.branch)


if __name__ == '__main__':  # pragma: no cover
    main()
