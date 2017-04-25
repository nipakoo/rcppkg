import git
import koji
import os
import pyrpkg
import shutil
import subprocess
import sys
import wget

import rcppkg.utils as rcppkg_utils

from . import cli
from distutils.dir_util import copy_tree
from pyrpkg.sources import SourcesFile
from pyrpkg.errors import HashtypeMixingError, rpkgError, rpkgAuthError, UnknownTargetError


class Commands(pyrpkg.Commands):
    def __init__(self, path, lookaside, lookasidehash, lookaside_cgi,
                 gitbaseurl, anongiturl, branchre, kojiconfig,
                 build_client, **kwargs):

        # Disable commands that haven't been tested/modified to work
        supported_commands = ['build', 'clone', 'container-build', 'mockbuild', 'new-sources', 'search']
        if sys.argv[1] not in supported_commands:
            print("This command is not supported yet. Use one of the following:")
            print(supported_commands)
            exit(0)

        super(Commands, self).__init__(path, lookaside, lookasidehash,
                                       lookaside_cgi, gitbaseurl, anongiturl,
                                       branchre, kojiconfig, build_client,
                                       **kwargs)
        if sys.argv[1] != 'search':
            self.setup_build_env()

    @property
    def build_dir(self):
        build_dir_name = "/ephemeral/rcppkgbuild"
        return build_dir_name

    @property
    def module_build_dir(self):
        module_build_dir_name = "%s/%s" % (self.build_dir, self.module_name)
        return module_build_dir_name

    @property
    def mock_results_dir(self):
        return os.path.join(self.module_build_dir, "results_%s" % self.module_name, self.ver, self.rel)

    @property
    def target(self):
        """This property ensures the target attribute"""
        return 'dist-foo'

    @property
    def arch(self):
        """This property ensures the arch attribute"""
        return 'x86_64'

    @property
    def spec_file_git(self):
        return self.gitbaseurl % {'module': self.module_name}


    def search_packages(self, search_word):
        matches = rcppkg_utils.get_matching_packages(search_word)
        for match in matches:
            print(match.name)

        exit(0)


    def setup_build_env(self):
        if not os.path.exists(self.module_build_dir):
            print("Fetching package list...")
            repo = rcppkg_utils.get_repository(self.module_name)
            if not repo:
                print("Spec file repository with name '%s' does not exists." % self.module_name)
                exit(0)

        print("Checking build environment...")
        if rcppkg_utils.remote_updates_available(self.module_build_dir):
            print("There are newer commits available in spec file repository remote.")
            question = "Do you want to abort this operation to go and fetch the latest changes?"
            if raw_input("%s (y/N) " % question).lower() == 'y':
                print("Aboring operation.")
                exit(0)

        if not os.path.exists(self.build_dir):
            os.mkdir(self.build_dir)
        if not os.path.exists(self.module_build_dir):
            os.mkdir(self.module_build_dir)

            try:
                os.system('git -C %s clone %s' % (self.build_dir, self.spec_file_git))
            except Exception as e:
                shutil.rmtree(self.module_build_dir)
                self.log.info("There is no spec file for a package with this name.")
                exit(0)
        print("Build environment set up successfully")


    def load_module_name(self):
        # If cloning, the module name is given as command line argument
        if sys.argv[1] == 'clone':
            self._module_name = sys.argv[-1]
            return

        # In case of other commands, current directory name should be module name
        dir_name = os.path.basename(os.getcwd())
        self._module_name = dir_name



    def git_clone(self, module, giturl, path=None,
                  branch=None, bare_dir=None,
                  anon=False, target=None):
        cmd = ['git', 'clone']
        if self.quiet:
            cmd.append('-q')
        # do the clone
        if branch and bare_dir:
            raise rpkgError('Cannot combine bare cloning with a branch')
        elif branch:
            # For now we have to use switch branch
            self.log.debug('Checking out a specific branch %s', giturl)
            cmd.extend(['-b', branch, giturl])
        elif bare_dir:
            self.log.debug('Cloning %s bare', giturl)
            cmd.extend(['--bare', giturl])
            if not target:
                cmd.append(bare_dir)
        else:
            self.log.debug('Cloning %s', giturl)
            cmd.extend([giturl])

        if not bare_dir:
            # --bare and --origin are incompatible
            cmd.extend(['--origin', self.default_branch_remote])

        if target:
            self.log.debug('Cloning into: %s', target)
            cmd.append(target)

        self._run_command(cmd, cwd=path)

        if self.clone_config:
            base_module = self.get_base_module(module)
            git_dir = target if target else bare_dir if bare_dir else base_module
            conf_git = git.Git(os.path.join(path, git_dir))
            self._clone_config(conf_git, module)



    def clone(self, module, path=None, branch=None, bare_dir=None,
              anon=False, target=None):
        """Clone a repo, optionally check out a specific branch.

        module is the name of the module to clone

        path is the basedir to perform the clone in

        branch is the name of a branch to checkout instead of <remote>/master

        bare_dir is the name of a directory to make a bare clone to, if this
        is a bare clone. None otherwise.

        target is the name of the folder in which to clone the repo

        Logs the output and returns nothing.

        """
        self.module_name = module
        if os.path.exists('%s/%s' % (self.path, self.module_name)):
            self.log.info('This package source already exists in current directory. Exiting.')
            exit(0)

        if not path:
            path = self.path
            self._push_url = None
            self._branch_remote = None
        
        specfile_path = '%s/%s.spec' % (self.module_build_dir, module)
        sources_file_path = '%s/sources' % self.module_build_dir

        if os.path.exists(sources_file_path):
            os.mkdir(self.module_name)
            sourcesf = self.get_source_entries()
            for entry in sourcesf.entries:
                os.system("wget %s/%s/%s/%s/%s/%s -P %s" % (self.lookaside, self.module_name, entry.file, entry.hashtype, entry.hash, entry.file, self.module_name))
                rcppkg_utils.compare_checksum(entry.hashtype, entry.hash, "%s/%s/%s" % (self.path, self.module_name, entry.file))
        else:
            url = rcppkg_utils.get_git_url_from_specfile(specfile_path)
            if url[-4:] == '.git':
                self.git_clone(module, url, path, branch,
                               bare_dir, anon, target)
            elif 'gerrite1' in url:
                self.git_clone(module, url, path, branch,
                               bare_dir, anon, target)
            else:
                self.log.info("No viable cloning method found ")
                exit(0)
        

    def load_rpmdefines(self):
        """Populate rpmdefines based on current active branch"""

        self._disttag = 'el%s' % self._distval
        self._rpmdefines = ["--define '_sourcedir %s'" % self.module_build_dir,
                            "--define '_specdir %s'" % self.module_build_dir,
                            "--define '_builddir %s'" % self.module_build_dir,
                            "--define '_srcrpmdir %s'" % self.module_build_dir,
                            "--define '_rpmdir %s'" % self.module_build_dir,
                            "--define 'dist .%s'" % self._disttag,
                            "--define '%s %s'" % (self._distvar,
                                                  self._distval),
                            # int and float this to remove the decimal
                            "--define '%s 1'" % self._disttag]

    def load_spec(self):
        """This sets the spec attribute"""

        deadpackage = False

        # Get a list of files in the path we're looking at
        files = os.listdir(self.module_build_dir)
        # Search the files for the first one that ends with ".spec"
        for f in files:
            if f.endswith('.spec') and f.startswith(self.module_name) and not f.startswith('.'):
                self._spec = f
                return
            if f == 'dead.package':
                deadpackage = True
        if deadpackage:
            raise rpkgError('No spec file found. This package is retired')
        else:
            raise rpkgError('No spec file found.')

    def load_nameverrel(self):
        """Set the release of a package module."""

        cmd = ['rpm']
        cmd.extend(self.rpmdefines)
        # We make sure there is a space at the end of our query so that
        # we can split it later.  When there are subpackages, we get a
        # listing for each subpackage.  We only care about the first.
        cmd.extend(['-q', '--qf', '"%{NAME} %{EPOCH} %{VERSION} %{RELEASE}??"',
                    '--specfile', '"%s/%s"' % (self.module_build_dir, self.spec)])
        joined_cmd = ' '.join(cmd)

        try:
            proc = subprocess.Popen(joined_cmd, shell=True,
                                    universal_newlines=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            output, err = proc.communicate()
        except Exception as e:
            if err:
                self.log.debug('Errors occoured while running following command to get N-V-R-E:')
                self.log.debug(joined_cmd)
                self.log.error(err)
            raise rpkgError('Could not query n-v-r of %s: %s'
                            % (self.module_name, e))
        if err:
            self.log.debug('Errors occoured while running following command to get N-V-R-E:')
            self.log.debug(joined_cmd)
            self.log.error(err)

        # Get just the output, then split it by ??, grab the first and split
        # again to get ver and rel
        first_line_output = output.split('??')[0]
        parts = first_line_output.split()
        if len(parts) != 4:
            raise rpkgError('Could not get n-v-r-e from %r'
                            % first_line_output)
        (self._module_name_spec,
         self._epoch,
         self._ver,
         self._rel) = parts

        # Most packages don't include a "Epoch: 0" line, in which case RPM
        # returns '(none)'
        if self._epoch == "(none)":
            self._epoch = "0"
    

    def srpm(self, hashtype=None):
        """Create an srpm using hashtype from content in the module

        Requires sources already downloaded.
        """

        specfile_path = '%s/%s.spec' % (self.module_build_dir, self.module_name)
        if (os.path.exists('%s/%s' % (self.module_build_dir, 'sources'))):
            sourcesf = self.get_source_entries()
            for entry in sourcesf.entries:
                source_package = "%s/%s" % (self.module_build_dir, entry.file)
                if os.path.exists(source_package):
                    os.remove(source_package)
                shutil.copyfile(entry.file, source_package)
        else:
            source_name = rcppkg_utils.get_source_from_specfile(self.module_name, self.ver, specfile_path)
            rcppkg_utils.create_source_package(self.path, self.module_build_dir, specfile_path, source_name)

        self.srpmname = os.path.join(self.module_build_dir,
                                     "%s-%s-%s.src.rpm"
                                     % (self.module_name, self.ver, self.rel))

        # See if we need to build the srpm
        if os.path.exists(self.srpmname):
            self.log.debug('Srpm found, rewriting it.')

        cmd = ['rpmbuild']
        cmd.extend(self.rpmdefines)
        if self.quiet:
            cmd.append('--quiet')
        # Figure out which hashtype to use, if not provided one
        if not hashtype:
            # Try to determine the dist
            hashtype = self._guess_hashtype()
        # This may need to get updated if we ever change our checksum default
        if not hashtype == 'sha256':
            cmd.extend(["--define '_source_filedigest_algorithm %s'"
                        % hashtype,
                        "--define '_binary_filedigest_algorithm %s'"
                        % hashtype])
        cmd.extend(['--nodeps', '-bs %s/%s' % (self.module_build_dir, self.spec)])
        self._run_command(cmd, shell=True)

    def load_kojisession(self, anon=False):
        """Initiate a koji session.

        The koji session can be logged in or anonymous
        """

        koji_config = self.read_koji_config()

        # save the weburl and topurl for later use as well
        self._kojiweburl = koji_config['weburl']
        self._topurl = koji_config['topurl']

        self.log.debug('Initiating a %s session to %s',
                       os.path.basename(self.build_client), koji_config['server'])

        # Build session options used to create instance of ClientSession
        session_opts = self.create_koji_session_opts(koji_config)

        try:
            session = koji.ClientSession(koji_config['server'], session_opts)
        except:
            raise rpkgError('Could not initiate %s session' % os.path.basename(self.build_client))
        else:
            self._kojisession = session

        self.login_koji_session(koji_config, self._kojisession)


    def mock_config(self, target=None, arch=None):
        """Generate a mock config based on branch data.

        Can use option target and arch to override autodiscovery.
        Will return the mock config file text.
        """

        if (target is None):
            target = self.target
        if (arch is None):
            arch = self.arch

        # Figure out if we have a valid build target
        build_target = self.kojisession.getBuildTarget(target)
        if not build_target:
            raise rpkgError('Unknown build target: %s\n'
                            'Consider using the --target option' % target)

        try:
            repoid = self.kojisession.getRepo(
                build_target['build_tag_name'])['id']
        except Exception:
            raise rpkgError('Could not find a valid build repo')

        proxy = '10.144.1.10:8080'
        with open("/etc/yum.conf") as f:
            for line in f:
                if 'proxy' in line:
                    proxy = line.split('=')[1]
        # Generate the config
        config = koji.genMockConfig('%s-%s' % (target, arch), arch,
                                    distribution=self.disttag,
                                    tag_name=build_target['build_tag_name'],
                                    repoid=repoid,
                                    topurl=self.topurl,
                                    yum_proxy=proxy)

        # Return the mess
        return(config)


    def build(self, skip_tag=False, scratch=False, background=False,
              url=None, chain=None, arches=None, sets=False, nvr_check=True):
        """Initiate a build of the module.  Available options are:

        skip_tag: Skip the tag action after the build

        scratch: Perform a scratch build

        background: Perform the build with a low priority

        url: A url to an uploaded srpm to build from

        chain: A chain build set

        arches: A set of arches to limit the scratch build for

        sets: A boolean to let us know whether or not the chain has sets

        nvr_check: A boolean; locally construct NVR and submit a build only if
                   NVR doesn't exist in a build system

        This function submits the task to koji and returns the taskID

        It is up to the client to wait or watch the task.
        """

        # Ensure the repo exists as well as repo data and site data
        # build up the command that a user would issue
        cmd = [self.build_client]
        # construct the url
        
        url = "git+" + self.spec_file_git +'?#' 
        if self.version_hash == None:
            url += rcppkg_utils.get_local_spec_head(self.module_build_dir)
        else:
            url += self.version_hash

        # Check to see if the target is valid
        build_target = self.kojisession.getBuildTarget(self.target)
        if not build_target:
            raise rpkgError('Unknown build target: %s' % self.target)
        # see if the dest tag is locked
        dest_tag = self.kojisession.getTag(build_target['dest_tag_name'])
        if not dest_tag:
            raise rpkgError('Unknown destination tag %s'
                            % build_target['dest_tag_name'])
        if dest_tag['locked'] and not scratch:
            raise rpkgError('Destination tag %s is locked' % dest_tag['name'])
        # If we're chain building, make sure inheritance works
        if chain:
            cmd.append('chain-build')
            ancestors = self.kojisession.getFullInheritance(
                build_target['build_tag'])
            ancestors = [ancestor['parent_id'] for ancestor in ancestors]
            if dest_tag['id'] not in [build_target['build_tag']] + ancestors:
                raise rpkgError('Packages in destination tag '
                                '%(dest_tag_name)s are not inherited by'
                                'build tag %(build_tag_name)s' %
                                build_target)
        else:
            cmd.append('build')
        # define our dictionary for options
        opts = {}
        # Set a placeholder for the build priority
        priority = None
        if skip_tag:
            opts['skip_tag'] = True
            cmd.append('--skip-tag')
        if scratch:
            opts['scratch'] = True
            cmd.append('--scratch')
        if background:
            cmd.append('--background')
            priority = 5  # magic koji number :/
        if arches:
            if not scratch:
                raise rpkgError('Cannot override arches for non-scratch '
                                'builds')
            for arch in arches:
                if not re.match(r'^[0-9a-zA-Z_.]+$', arch):
                    raise rpkgError('Invalid architecture name: %s' % arch)
            cmd.append('--arch-override=%s' % ','.join(arches))
            opts['arch_override'] = ' '.join(arches)

        cmd.append(self.target)

        if url.endswith('.src.rpm'):
            srpm = os.path.basename(url)
            build_reference = srpm
        else:
            try:
                build_reference = self.nvr
            except rpkgError as error:
                self.log.warning(error)
                if nvr_check:
                    self.log.info('Note: You can skip NVR construction & NVR'
                                  ' check with --skip-nvr-check. See help for'
                                  ' more info.')
                    raise rpkgError('Cannot continue without properly constructed NVR.')
                else:
                    self.log.info('NVR checking will be skipped so I do not'
                                  ' care that I am not able to construct NVR.'
                                  '  I will refer this build by package name'
                                  ' in following messages.')
                    build_reference = self.module_name

        # Now submit the task and get the task_id to return
        # Handle the chain build version
        if chain:
            self.log.debug('Adding %s to the chain', url)
            # If we're dealing with build sets the behaviour of the last
            # package changes, and we add it to the last (potentially empty)
            # set.  Otherwise the last package just gets added to the end of
            # the chain.
            if sets:
                chain[-1].append(url)
            else:
                chain.append([url])
            # This next list comp is ugly, but it's how we properly get a :
            # put in between each build set
            cmd.extend(' : '.join([' '.join(build_sets) for build_sets in chain]).split())
            self.log.info('Chain building %s + %s for %s', build_reference, chain[:-1], self.target)
            self.log.debug('Building chain %s for %s with options %s and a priority of %s',
                           chain, self.target, opts, priority)
            self.log.debug(' '.join(cmd))
            task_id = self.kojisession.chainBuild(chain, self.target, opts, priority=priority)
        # Now handle the normal build
        else:
            cmd.append(url)
            self.log.info('Building %s for %s', build_reference, self.target)
            self.log.debug('Building %s for %s with options %s and a priority of %s',
                           url, self.target, opts, priority)
            self.log.debug(' '.join(cmd))
            task_id = self.kojisession.build(url, self.target, opts, priority=priority)
        self.log.info('Created task: %s', task_id)
        self.log.info('Task info: %s/taskinfo?taskID=%s', self.kojiweburl, task_id)
        return task_id


    def container_build_koji(self, target_override=False, opts={},
                                 kojiconfig=None, build_client=None,
                                 koji_task_watcher=None,
                                 nowait=False):
        # check if repo is dirty and all commits are pushed
        #self.check_repo()
        docker_target = self.target
        if not target_override:
            # Translate the build target into a docker target,
            # but only if --target wasn't specified on the command-line
            docker_target = '%s-docker-candidate' % self.target.split('-candidate')[0]

        koji_session_backup = (self.build_client, self.kojiconfig)
        (self.build_client, self.kojiconfig) = (build_client, kojiconfig)

        try:
            self.load_kojisession()
            if "buildContainer" not in self.kojisession.system.listMethods():
                raise RuntimeError("Kojihub instance does not support buildContainer")

            build_target = self.kojisession.getBuildTarget(docker_target)
            if not build_target:
                msg = "Unknown build target: %s" % docker_target
                self.log.error(msg)
                raise UnknownTargetError(msg)
            else:
                dest_tag = self.kojisession.getTag(build_target['dest_tag'])
                if not dest_tag:
                    self.log.error("Unknown destination tag: %s", build_target['dest_tag_name'])
                if dest_tag['locked'] and 'scratch' not in opts:
                    self.log.error("Destination tag %s is locked", dest_tag['name'])

            url = "git+" + self.spec_file_git +'?#'
            url += rcppkg_utils.get_local_spec_head(self.module_build_dir)
            source = url

            task_opts = {}
            for key in ('scratch', 'name', 'version', 'release',
                        'yum_repourls', 'git_branch'):
                if key in opts:
                    task_opts[key] = opts[key]
            priority = opts.get("priority", None)

            task_id = self.kojisession.buildContainer(source,
                                                      docker_target,
                                                      task_opts,
                                                      priority=priority)

            self.log.info('Created task: %s', task_id)
            self.log.info('Task info: %s/taskinfo?taskID=%s', self.kojiweburl, task_id)
            if not nowait:
                rv = koji_task_watcher(self.kojisession, [task_id])
                if rv == 0:
                    result = self.kojisession.getTaskResult(task_id)
                    try:
                        result["koji_builds"] = [
                            "%s/buildinfo?buildID=%s" % (self.kojiweburl,
                                                         build_id)
                            for build_id in result.get("koji_builds", [])]
                    except TypeError:
                        pass
                    log_result(self.log.info, result)

        finally:
            (self.build_client, self.kojiconfig) = koji_session_backup
            self.load_kojisession()


    def get_source_entries(self):
        sources_file = "%s/sources" % self.module_build_dir

        if not os.path.exists(sources_file):
            self.log.info("sources file doesn't exist. Source files download skipped.")
            exit(0)

        return SourcesFile(sources_file, self.source_entry_type)


    def upload(self, packages, replace=False):
        """Upload source file(s) in the lookaside cache

        Can optionally replace the existing tracked sources
        """
        FEDORA_PACKAGE_BASE_URL = "http://pkgs.fedoraproject.org/repo/pkgs"

        package = self.module_name
        fedora_package_url = "%s/%s/" % (FEDORA_PACKAGE_BASE_URL, package)

        work_dir = "/tmp/%s" % package
        if not os.path.exists(work_dir):
            os.mkdir(work_dir)
        else:
            self.log.info("Directory with work directory name %s already exists locally" % work_dir)
            exit(0)

        sourcesf = self.get_source_entries()
        tails = []

        for entry in sourcesf.entries:
            file = entry.file
            source_url = "%s%s/" % (fedora_package_url, file)
            rcppkg_utils.find_link_tails(tails, file, source_url)

        for tail in tails:
            source_path = "".join(tail.split("/repo/pkgs/%s/" % package)[1:])
            dir_tree = "%s/%s" % (work_dir, "/".join(source_path.split('/')[:-1]))

            os.makedirs(dir_tree)
            os.system("wget %s -P %s" % (tail, dir_tree))

        os.system("scp -r %s %s" % (work_dir, self.lookaside_cgi))
        shutil.rmtree(work_dir)
        