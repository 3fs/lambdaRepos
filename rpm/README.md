#  AWS Lambda YUM repository manager for S3

Automatic YUM repository building inside S3 bucket using with lambda support

## Readme contents

* [Setting up code, S3 and Lambda](#setting-up-code-s3-and-lambda)
    * [Getting the code](#getting-the-code)
    * [GPG key](#gpg-key)
    * [Environmental variables](#environmental-variables)
    * [Set up role](#set-up-role)
    * [Set up lambda with CLI](#set-up-lambda-with-cli)
    * [Set up lambda manually](#set-up-lambda-manually)
    * [The triggers](#the-triggers)
    * [Set up S3](#set-up-s3)
* [Setting up yum](#setting-up-yum)
    * [First time set up](#first-time-set-up)
    * [Install/update](#installupdate)
* [Notes](#notes)
* [Tests](#tests)

## Setting up code, S3 and Lambda

### Getting the code
Clone the repo, get all other required files and compress them
```
git clone https://github.com/tactycal/lambdaRepos.git
cd lambdaRepos/rpm
make all
```

### GPG key
create your gpg key (skip to exporting your key, if you already have it)
```
gpg --gen-key
# Follow the instructions
# Create 'RSA and RSA' key - option 1
# For maxium encryption it is recommended to make 4096 bits long key
# Key should not expire
```

export your key

```
gpg --export-secret-key -a "User Name" > secret.key  # exports secret key to secret.key
```

### Set up role

Create new role with s3 write/read access

Here is a minimal requirement for the policy that is included in role:
```
{"Version": "2012-10-17",
    "Statement": [
        {"Sid": "<THIS IS UNIQE>",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:PutObjectAcl"],
            "Effect": "Allow",
            "Resource": "arn:aws:s3:::<YOUR BUCKET NAME>/*"}]}
```

### Environmental variables
These are the environmental variables you will have to set:

| Key | Value |
| --- | ---|
| PUBLIC | True/False |
| GPG_KEY | File |
| GPG_PASS | GPG key password |
| BUCKET_NAME | Bucket Name |
| REPO_DIR | Directory |

**PUBLIC** Set to True for the outputs to be publicly readable

**GPG_KEY** Location of your GPG private key from root of the bucket (e.g. secret/private.key). Not providing this variable will cause lambda to skip GPG singing

**GPG_PASS** Password of private key uploaded to GPG_KEY (Note: environmental variables are/can be encrypted using KMS keys)

**BUCKET_NAME** Name of the bucket. Should be the same as the one selected in triggers and the one you're using for repository

**REPO_DIR** Path to repositroy from bucket root. If none is set, it is assumed root of repository is root of the bucket

### Set up lambda with CLI

[Install aws cli](http://docs.aws.amazon.com/cli/latest/userguide/installing.html)

Create new lambda function:
```
aws lambda create-function \
    --function-name <name the function> \
    --zip-file fileb://code.zip \
    --role <role's arn> \    # arn from role with S3 read/write access
    --handler s3rpm.handler \
    --runtime python3.6 \
# Replace '<...>' with environmental variables
    --environment Variables='{PUBLIC=<bool>, GPG_KEY=<file>, GPG_PASS=<password>, BUCKET_NAME=<bucket name>, REPO_DIR=<dir>}'
```

### Set up lambda manually

If CLI is not your thing, then you can upload code manaully

Create new lambda function, set handler to **s3rpm.lambda_handler**, runtime to **python 3.6**

Upload `code.zip` to lambda function

### The triggers

 * Object Created(All), suffix 'rpm'
 * Object Removed(All), suffix 'rpm'
 * If you are using certain directory as a repo, set it as prefix

### Set up S3
Upload secret key file to location you specified as GPG_KEY

Upload .rpm file to desired folder, lambda function should now keep your repository up to date

## Setting up yum

### First time set up

create `example.repo` file in `/etc/yum.repos.d/example.repo` 
```
vi /etc/yum.repos.d/example.repo
```
with following contents:
```
[reponame]
name=Repo name
baseurl=https://s3.$AWS_SERVER.amazonaws.com/$BUCKET_NAME/$PATH_TO_REPO
enabled=1
gpgcheck=0
repo_gpgcheck=1
gpgkey=<link to public key of key you used for signing metadata files>
```

* You can do `repo_gpgcheck=0` to skip gpg verification when installing packages
* You can do `gpgcheck=1` if you are uploading signed rpm packages(lambda does not sign them, it signs only metadata xml file)

### Install/update
Install package
```
sudo yum install <package name>
```

Upgrading package
```
sudo yum upgrade
```

## Notes

* .rpm and repodata/* in repository directory are and should be publicly accessible for the 

* Don't forget to increase the timeout of lambda function

* If somebody tries to inject a malicious rpm file in your repo it will be automaticly added to repository. It is your job to make bucket secure enough for this not to happen.!!!

## Tests

To run unit tests:
```
make requires   #gets dependancies
make test       #runs the tests
```
