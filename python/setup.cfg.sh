#!/bin/bash
VERSION=`python -c "import rqse; print('.'.join(map(str,rqse.__version__)))"`
AUTHOR=`python -c "import rqse; print(rqse.__author__)"`
EMAIL=`python -c "import rqse; print(rqse.__author_email__)"`
DESCRIPTION="RQse: Queued System Events for Redis"
REQUIRES=`python -c "list(map(print,['\t'+line.strip() for line in open('requirements.txt', 'r').readlines()]))"`
cat <<EOF > setup.cfg
[metadata]
name = rqse
version = ${VERSION}
author = ${AUTHOR}
author_email = ${EMAIL}
description = ${DESCRIPTION}
license = Apache License 2.0
url = https://github.com/alexmilowski/rqse

[options]
packages =
   rqse
include_package_data = True
install_requires =
${REQUIRES}

[options.package_data]
* = *.json, *.yaml

EOF
