
#  AWS Lambda APT repository manager for S3

Rewrite of [szinck/s3apt](https://github.com/szinck/s3apt) with a few changes and extra features - Release file is being generated and is signed with GPG key provided

## Setting up S3 and Lambda

Clone the repo and get all other required files
```
git clone https://github.com/tactycal/lambdaRepos.git
cd lambdaRepos/deb
pip install -t . -r requirements.txt
```

Compress all needed files
```
zip code.zip s3apt.py gnupg.py debian/*
```
Or just use `make set` instead of `zip` and `pip` command

Presuming you already have GPG key generated export secret key (you can skip this part if you don't want to GPG sign your repository)
```
gpg -a --export-secret-key > secret.key
```

Create new lambda function, set handler to **s3apt.lambda_handler**, runtime to **python 2.7** and triggers to:

 * Object Created(All), suffix 'deb'
 * Object Removed(All), suffix 'deb'
 * If you are using certain directory as a repo, set it as prefix

Upload `code.zip` to lambda function

Set the environmental variables

| Key | Value |
| --- | ---|
| PUBLIC | True/False |
| GPG_KEY | File |
| GPG_PASS | GPG key password |
| BUCKET_NAME | Bucket Name |
| CACHE_PREFIX | Directory |

**PUBLIC** Set to `True` for the outputs to be publicly readable

**GPG_KEY** Location of your GPG private key from root of the bucket (e.g. secret/private.key). Not providing this variable will cause lambda to skip GPG singing

**GPG_PASS** Password of private key uploaded to GPG_KEY (Note: environmental variables are/can be encrypted using KMS keys)

**BUCKET_NAME** Name of the bucket. Should be the same as the one selected in triggers and the one you're using for repository

**CACHE_PREFIX** Path to folder for packages cache(e.g. deb/cache)

Make folder in your S3 bucket with the same name as CACHE_PREFIX variable

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

.deb, Release and Package files are and should be publicly accessible for previously mentioned method of setting up apt's sources list to work, if you don't want them to be, then change PUBLIC in environment variables to False and refer to szinck's guide [here](http://webscale.plumbing/managing-apt-repos-in-s3-using-lambda)

If somebody tries to inject a malicious deb file in your repo it will be automaticly added to repository. It is your job to make bucket secure enough for this not to happen.!!!

**You should change lambda timeout to 10 seconds or more to make sure that function will work**
