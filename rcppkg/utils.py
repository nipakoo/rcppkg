import git
import gitlab
import os
import shutil
import subprocess
import sys

from distutils.dir_util import copy_tree
from HTMLParser import HTMLParser


def get_gitlab_connection():
    # TODO USERS OWN TOKEN
    return gitlab.Gitlab('GITLAB BASE URL', 'ACCESS TOKEN')


def get_gitlab_group():
    gl = get_gitlab_connection()
    # TODO REMOVE GROUP ID HARDCODE
    return gl.groups.get('GROUP ID')


def get_matching_packages(search_word):
    group = get_gitlab_group()
    projects = group.projects.list(all=True)

    matches = []
    for project in projects:
        if search_word.lower() in project.name.lower():
            matches.append(project)
    return matches


def get_repository(search_word):
    matches = get_matching_packages(search_word)
    for match in matches:
        if search_word == match.name:
            return match

    return False


def remote_updates_available(module_build_dir):
    if not os.path.exists(module_build_dir):
        return False
        
    os.system('git -C %s remote update' % module_build_dir)
    git_cmd = 'git -C %s status -uno' % module_build_dir
    if 'branch is behind' in subprocess.check_output([git_cmd], shell=True, stderr=subprocess.STDOUT):
        return True

    return False


def get_git_url_from_specfile(specfile_path):
    with open(specfile_path) as specfile:
        for line in specfile:
            if 'URL:' in line:
                url_line = line.split('URL:')
                return url_line[1].strip()

    print('Did not find a matching repository')
    sys.exit(1)


def get_source_from_specfile(module_name, version, specfile_path):
    file_extension = None
    with open(specfile_path) as specfile:
        for line in specfile:
            if 'Source:' in line or 'Source0:' in line:
                source_name = line.split(':')[-1].strip().split('/')[-1]
                if '%{name}' in source_name:
                    source_name = source_name.replace('%{name}', module_name)
                if '%{version}' in source_name:
                    source_name = source_name.replace('%{version}', version)
                return source_name

    print("Could not find source name from spec file")
    sys.exit(0)


def get_file_extension_from_name(tarball_name):
    if tarball_name[-3:] == '.gz' or tarball_name[-3:] == '.xz':
        return tarball_name[-7:]
    elif tarball_name[-4:] == '.tgz':
        return tarball_name[-4:]
    elif tarball_name[-4:] == '.bz2':
        return tarball_name[-8:]

    return ''


def compress_to_dir(target_dir, tarball_name, source_dir, file_extension):
    tar_opt = ''
    if file_extension == '.tar.gz' or file_extension == '.tgz':
        tar_opt = '-czf'
    elif file_extension == '.tar.xz':
        tar_opt = '-cJf'
    elif file_extension == '.tar.bz2':
        tar_opt = '-cjf'

    tar_cmd = 'tar -C %s %s %s %s' % (target_dir, tar_opt, tarball_name, source_dir)
    os.system(tar_cmd)


def create_source_package(curdir, module_build_dir, specfile_path, source_name):
    source_target_dir = '/'.join(specfile_path.split('/')[:-1])
    file_extension = get_file_extension_from_name(source_name)

    source_package = "%s/%s" % (module_build_dir, source_name)
    source_dir = source_name.replace(file_extension, '')
    
    tmp_source_dir = "%s/%s" % (source_target_dir, source_dir)

    if os.path.exists(tmp_source_dir):
        shutil.rmtree(tmp_source_dir)
    if os.path.exists(source_package):
        os.remove(source_package)

    os.makedirs(tmp_source_dir)
    copy_tree(curdir, tmp_source_dir)
    compress_to_dir(source_target_dir, source_package, source_dir, file_extension)

    shutil.rmtree(tmp_source_dir)


def get_local_spec_head(module_build_dir):
    repo = git.Repo(module_build_dir)
    return repo.heads[0].commit.hexsha


def find_link_tails(tails, file_name, url):
    curl_cmd = "curl %s" % url
    index = subprocess.check_output([curl_cmd], shell=True, stderr=subprocess.STDOUT)
    parser = LinkHTMLParser()
    parser.feed(index)

    start_index = find_files_start(parser.links)
    files = parser.links[start_index:]

    for file in files:
        new_url = '%s%s' % (url, file)
        if (file == file_name):
            tails.append(new_url)
        else:
            find_link_tails(tails, file_name, new_url)


def find_files_start(files):
    for file in files:
        if '/repo/pkgs/' in file:
            return files.index(file) + 1

    return -1


def compare_checksum(hashtype, stored_hash, file):
    hash_cmd = ''
    if hashtype == 'md5':
        hash_cmd = "md5sum %s | cut -d ' ' -f1" % file
    elif hashtype == 'sha512':
        hash_cmd = "sha512sum %s | cut -d ' ' -f1" % file
    checksum = subprocess.check_output([hash_cmd], shell=True, stderr=subprocess.STDOUT)

    if stored_hash.strip() != checksum.strip():
        print("Checksum mismatch detected. Deleting faulty file.")
        os.remove(file)


class LinkHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(attrs[0][1])
