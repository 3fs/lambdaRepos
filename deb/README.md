#  AWS Lambda APT repository manager for S3

Rewrite of [szinck/s3apt](https://github.com/szinck/s3apt) with a few changes and extra features - Release file is being generated and is signed with GPG key provided

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
* [Setting up apt](#setting-up-apt)
* [Notes](#notes)

## Setting up code, S3 and Lambda

### Getting the code
Clone the repo, get all other required files and compress them
```
git clone https://github.com/tactycal/lambdaRepos.git
cd lambdaRepos/deb
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
        {"Sid": "<THIS IS UNIQUE>",
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
| CACHE | Directory |

**PUBLIC** Set to `True` for the outputs to be publicly readable

**GPG_KEY** Location of your GPG private key from root of the bucket (e.g. secret/private.key). Not providing this variable will cause lambda to skip GPG singing

**GPG_PASS** Password of private key uploaded to GPG_KEY (Note: environmental variables are/can be encrypted using KMS keys)

**BUCKET_NAME** Name of the bucket. Should be the same as the one selected in triggers and the one you're using for repository

**CACHE** Path to folder for packages cache(e.g. deb/cache)

### Set up lambda with CLI

[Install aws cli](http://docs.aws.amazon.com/cli/latest/userguide/installing.html)

Create new lambda function:
```
aws lambda create-function \
    --function-name <name the function> \
    --zip-file fileb://code.zip \
    --role <role's arn> \    # arn from role with S3 read/write access
    --handler s3apt.lambda_handler \
    --runtime python2.7 \
# Replace '<...>' with environmental variables
    --environment Variables='{PUBLIC=<bool>, GPG_KEY=<file>, GPG_PASS=<password>, BUCKET_NAME=<bucket name>, CACHE=<dir>}'
```

### Set up lambda manually

If CLI is not your thing, then you can upload code manaully

Create new lambda function, set handler to **s3apt.lambda_handler**, runtime to **python 2.7**

Upload `code.zip` to lambda function

### The triggers

 * Object Created(All), suffix 'deb'
 * Object Removed(All), suffix 'deb'
 * If you are using certain directory as a repo, set it as prefix

### Set up S3
Make folder in your S3 bucket with the same name as CACHE variable

Upload secret key file to location you specified as GPG_KEY


Upload .deb file to desired folder, lambda function should now keep your repository up to date

## Setting up apt

First time set up
```
sudo echo "deb https://s3.$AWS_SERVER.amazonaws.com/$BUCKET_NAME/$PATH_TO_FOLDER_WITH_DEBIAN_FILES /" >> /etc/apt/sources.list
#an example of link "https://s3.eu-central-1.amazonaws.com/testbucket/repo"
#add public key to trusted sources - you have to export public key or use key server
apt-key add <path to key>
sudo apt update
sudo apt install <packages>
```

Upgrading package
```
sudo apt update
sudo apt upgrade
```

## Notes

 * .deb, Release and Package files are and should be publicly accessible for previously mentioned method of setting up apt's sources list to work, if you don't want them to be, then change PUBLIC in environment variables to False and refer to szinck's guide [here](http://webscale.plumbing/managing-apt-repos-in-s3-using-lambda)
 * If somebody tries to inject a malicious deb file in your repo it will be automaticly added to repository. It is your job to make bucket secure enough for this not to happen.!!!
 * **You should change lambda timeout to more than 10 seconds to make sure that function will work**
