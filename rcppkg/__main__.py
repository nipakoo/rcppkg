import logging
import os
import six
import sys
if six.PY3:  # SafeConfigParser == ConfigParser, former deprecated in >= 3.2
    from six.moves.configparser import ConfigParser
else:
    from six.moves.configparser import SafeConfigParser as ConfigParser

import rcppkg
import pyrpkg


cli_name = os.path.basename(sys.argv[0])


def main():
    config = ConfigParser()
    config.read('/etc/rpkg/%s.conf' % cli_name)
    
    client = rcppkg.cli.rcppkgClient(config, name=cli_name)
    client.do_imports(site='rcppkg')
    client.parse_cmdline()

    try:
        client.args.path = pyrpkg.utils.getcwd()
    except:
        print('Could not get current path, have you deleted it?')
        sys.exit(1)

    log = pyrpkg.log
    client.setupLogging(log)
    log.setLevel(logging.DEBUG)

    try:
        sys.exit(client.args.command())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()