# lambdaRepos
POC for managing RPM and DEB repositories using aws' S3 and λ

# Info
Code for managing `yum`(rpm) repository is located in [rpm folder](https://github.com/tactycal/lambdaRepos/tree/master/rpm)

Code for managing `apt`(deb) repository is located in [deb folder](https://github.com/tactycal/lambdaRepos/tree/master/deb)

Both folders contain more detailed info on setting up S3 bucket and lambda function, that keeps your repo in sync with provided packages

## Combining with TravisCI

It is possible to automate deployment of packages by combining this repository with Travis CI.

Examples of `.travis.yml` and `Makefile` used for autamatic deployment of go project can be found in repository