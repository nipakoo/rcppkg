## HOW TO INSTALL

# This script has been removed due to protect internal information
$ ./rcppkg_install.sh


## HOW TO USE

$ rcppkg clone <package_name>
- package sources will be cloned to your working directory
- package spec file repository will be cloned to /ephemeral/rcppkgbuild/<package_name>

$ rcppkg local
- will make a local build
- uses sources from your current dir and spec file from /ephemeral/rcppkgbuild/<current_directory_name>

$ rcppkg mockbuild
- will make a local build
- uses chroot environment created by mock to resolve package dependencies
- uses sources from your current dir and spec file from /ephemeral/rcppkgbuild/<current_directory_name>

$ rcppkg build 
- will make a kbuild to the koji server
- uses chroot environment created by mock to resolve package dependencies
- uses spec file from the last commit in your /ephemeral/rcppkgbuild/<current_directory_name>
- you can also specify a git hash (of spec file repository commit) after build
(for example $ rcppkg build 403abdc48c91cc30bc6a8e923ae09956841d9952)
to make a build based on specific spec file commit

$ rcppkg new-sources
- checks out the spec file repository of current package (directory you are in) into /ephemeral/rcppkgbuild
- goes through the files listed in 'sources'-file there
- fetches those files from fedora package repository and copy then to SOURCE SERVER (or other lookaside if changed)

$ rcppkg search <search word>
- fetches all the projects under the git group used to store spec file repositories
- compares <search word> against the results and prints the repository names that <search word> is found in

