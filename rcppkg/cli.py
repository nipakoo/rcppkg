import os

from pyrpkg.cli import cliClient
from pyrpkg.errors import rpkgError

class rcppkgClient(cliClient):
    def __init__(self, config, name=None):
        self.DEFAULT_CLI_NAME = 'rcppkg'
        super(rcppkgClient, self).__init__(config, name)

    def setup_subparsers(self):
        """Setup basic subparsers that all clients should use"""

        # Setup some basic shared subparsers

        # help command
        self.register_help()

        # Add a common parsers
        self.register_build_common()
        self.register_rpm_common()

        # Other targets
        self.register_build()
        self.register_chainbuild()
        self.register_clean()
        self.register_clog()
        self.register_clone()
        self.register_copr_build()
        self.register_commit()
        self.register_compile()
        self.register_container_build()
        self.register_container_build_setup()
        self.register_diff()
        self.register_gimmespec()
        self.register_gitbuildhash()
        self.register_giturl()
        self.register_import_srpm()
        self.register_install()
        self.register_lint()
        self.register_local()
        self.register_mockbuild()
        self.register_mock_config()
        self.register_new()
        self.register_new_sources()
        self.register_patch()
        self.register_prep()
        self.register_pull()
        self.register_push()
        self.register_scratch_build()
        self.register_sources()
        self.register_srpm()
        self.register_switch_branch()
        self.register_tag()
        self.register_unused_patches()
        self.register_upload()
        self.register_verify_files()
        self.register_verrel()
        self.register_search()

    def load_cmd(self):
        """This sets up the cmd object"""

        # Set target if we got it as an option
        target = None
        if hasattr(self.args, 'target') and self.args.target:
            target = self.args.target

        # load items from the config file
        items = dict(self.config.items(self.name, raw=True))

        try:
            dg_namespaced = self.config.getboolean(self.name,
                                                   "distgit_namespaced")
        except ValueError:
            raise rpkgError('distgit_namespaced option must be a boolean')
        except configparser.NoOptionError:
            dg_namespaced = False

        # Read comma separated list of kerberos realms
        realms = [realm
                  for realm in items.get("kerberos_realms", '').split(',')
                  if realm]

        # Create the cmd object
        self._cmd = self.site.Commands(self.args.path,
                                       items['lookaside'],
                                       items['lookasidehash'],
                                       items['lookaside_cgi'],
                                       items['gitbaseurl'],
                                       items['anongiturl'],
                                       items['branchre'],
                                       items['kojiconfig'],
                                       items['build_client'],
                                       user=self.args.user,
                                       dist=self.args.dist or self.args.release,
                                       target=target,
                                       quiet=self.args.q,
                                       distgit_namespaced=dg_namespaced,
                                       realms=realms
                                       )

        self._cmd.module_name = self.args.module_name
        self._cmd.password = self.args.password
        self._cmd.runas = self.args.runas
        self._cmd.debug = self.args.debug
        self._cmd.verbose = self.args.v
        self._cmd.clone_config = items.get('clone_config')

        if hasattr(self.args, 'version_hash'):
        	self._cmd.version_hash = self.args.version_hash

    def register_build(self):
        """Register the build target"""

        build_parser = self.subparsers.add_parser(
            'build', help='Request build', parents=[self.build_parser_common],
            description='This command requests a build of the package in the '
                        'build system. By default it discovers the target '
                        'to build for based on branch data, and uses the '
                        'latest commit as the build source.')
        build_parser.add_argument(
            '--skip-nvr-check', action='store_false', default=True,
            dest='nvr_check',
            help='Submit build to buildsystem without check if NVR was '
                 'already build. NVR is constructed locally and may be '
                 'different from NVR constructed during build on builder.')
        build_parser.add_argument(
            '--skip-tag', action='store_true', default=False,
            help='Do not attempt to tag package')
        build_parser.add_argument(
            '--scratch', action='store_true', default=False,
            help='Perform a scratch build')
        build_parser.add_argument(
            '--srpm', nargs='?', const='CONSTRUCT',
            help='Build from an srpm. If no srpm is provided with this option'
                 ' an srpm will be generated from current module content.')
        build_parser.add_argument(
            'version_hash', default=None, nargs='?', help='Hash of the spec file commit to be built.')
        build_parser.set_defaults(command=self.build)

    def container_build_koji(self):
        target_override = False
        # Override the target if we were supplied one
        if self.args.target:
            self.cmd._target = self.args.target
            target_override = True

        # TODO REMOVE BRANCH HARDCORDING
        opts = {"scratch": self.args.scratch,
                "quiet": self.args.q,
                "yum_repourls": self.args.repo_url,
                "git_branch": "master"}

        section_name = "%s.container-build" % self.name
        err_msg = "Missing {option} option in [{plugin.section}] section. "\
                  "Using {option} from [{root.section}]"
        err_args = {"plugin.section": section_name, "root.section": self.name}

        if self.config.has_option(section_name, "kojiconfig"):
            kojiconfig = self.config.get(section_name, "kojiconfig")
        else:
            err_args["option"] = "kojiconfig"
            self.log.debug(err_msg % err_args)
            kojiconfig = self.config.get(self.name, "kojiconfig")

        if self.config.has_option(section_name, "build_client"):
            build_client = self.config.get(section_name, "build_client")
        else:
            err_args["option"] = "kojiconfig"
            self.log.debug(err_msg % err_args)
            build_client = self.config.get(self.name, "build_client")

        self.cmd.container_build_koji(target_override, opts=opts,
                                      kojiconfig=kojiconfig,
                                      build_client=build_client,
                                      koji_task_watcher=self._watch_koji_tasks,
                                      nowait=self.args.nowait)

    def register_new_sources(self):
        """Register the new-sources target"""

        # Make it part of self to be used later
        self.new_sources_parser = self.subparsers.add_parser(
            'new-sources', help='Upload new source files',
            description='This will upload new source files to the lookaside '
                        'cache and remove any existing ones. The "sources" '
                        'and .gitignore files will be updated with the new '
                        'uploaded file(s).')
        self.new_sources_parser.add_argument('packages', nargs='*')
        self.new_sources_parser.set_defaults(command=self.new_sources, replace=True)

    def new_sources(self):
        self.cmd.upload(self.args.packages, replace=self.args.replace)
        self.log.info("Source upload succeeded.")

    def mockbuild(self):
        mockargs = []

        if self.args.no_clean or self.args.no_clean_all:
            mockargs.append('--no-clean')

        if self.args.no_cleanup_after or self.args.no_clean_all:
            mockargs.append('--no-cleanup-after')

        # Pick up any mockargs from the env
        try:
            mockargs += os.environ['MOCKARGS'].split()
        except KeyError:
            # there were no args
            pass
        self.cmd.mockbuild(mockargs, self.args.root, hashtype=self.args.hash)

    def register_search(self):
        self.search_parser = self.subparsers.add_parser(
            'search', help='Search for packages',
            description='Search for available packages based on keyword given')
        self.search_parser.add_argument('search_word', nargs='?')
        self.search_parser.set_defaults(command=self.search)

    def search(self):
        self.cmd.search_packages(self.args.search_word)

