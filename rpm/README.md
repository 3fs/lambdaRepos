#  AWS Lambda YUM repository manager for S3

Automatic YUM repository building inside S3 bucket using with lambda support

## Setting up S3 and Lambda

Clone the repo and get all other required files
```
git clone https://github.com/tactycal/lambdaRepos.git
cd lambdaRepos/rpm
pip3 install -t . -r requirements.txt
```

Compress all needed files
```
zip code.zip s3rpm.py gnupg.py pyrpm/* pyrpm/tools/*
```

Or just use `make set` instead of `zip` and `pip3` command

Presuming you already have GPG key generated export secret key(you can skip this part if you don't want to GPG sign your repository)
```
gpg -a --export-secret-key > secret.key
```

Create new lambda function, set handler to **s3rpm.lambda_handler**, runtime to **python 3.6** and the triggers to:

 * Object Created, suffix 'rpm'
 * Object Removed, suffix 'rpm'
 * If you are using certain directory as a repo, set it as prefix

Upload `code.zip` to lambda function

Set the environmental variables

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


Upload secret key file to location you specified as GPG_KEY

Upload GPG SIGNED .rpm file to desired folder, lambda function should now keep your repository up to date

## Setting up yum

**First time set up**

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
*You can do `repo_gpgcheck=0` to skip gpg verification when installing packages
*You can do `gpgcheck=1` if you are uploading signed rpm packages(lambda does not sign them, it signs only metadata xml file)

Install package
```
su
yum install <package name>
```

Upgrading package
```
su
yum upgrade
```

## Notes

.rpm and repodata/* in repository directory are and should be publicly accessible

If somebody tries to inject a malicious rpm file in your repo it will be automaticly added to repository. It is your job to make bucket secure enough for this not to happen.!!!