from __future__ import print_function
from pyrpm.rpm import RPM
from pyrpm.yum import YumPackage
from pyrpm.tools.createrepo import YumRepository
import boto3
import os
import botocore
import gnupg
import json
import shutil
def lambda_handler(event, context):
    s3 = boto3.client('s3')

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    repo = YumRepository('/tmp/repo/') # set repository
    prefix = '/'.join(key.split('/')[0:-1])+'/'

    if os.environ['REPO_DIR'].endswith('/'):
        os.environ['REPO_DIR'] = os.environ['REPO_DIR'][:-1]
    if os.environ['REPO_DIR'].startswith('/'):
        os.environ['REPO_DIR'] = os.environ['REPO_DIR'][1:]

    #make sure we are working with correct files
    if bucket == os.environ['BUCKET_NAME'] and key.endswith(".rpm") and prefix.startswith(os.environ['REPO_DIR']):
        #check if repodata already exist, if not create new with key file
        print('Bucket and key\'s file accepted')
        exists = check_bucket_file_existance(os.environ['REPO_DIR']+'/repodata/repomd.xml')
        files = ['repomd.xml', 'primary.xml.gz','filelists.xml.gz', 'other.xml.gz']
        
        #make /tmp/repodata path
        if not os.path.exists(repo.repodir+'/repodata/'):
            os.makedirs(repo.repodir+'/repodata/')

        # if repodata files exist download them to /tmp where we can manipulate with them
        if exists: 
            print('repodata already exists, old files will be overwriten')
            for f in files:
                s3.download_file(os.environ['BUCKET_NAME'], os.environ['REPO_DIR']+'/repodata/'+f, repo.repodir+'repodata/'+f)
            repo.read()
        print('Creating Metadata files')
        repo, cache = check_changed_files(repo)
        #Check if object was removed

        repo.save()

        #sign metadata
        if not os.environ['GPG_KEY']=='':
            sign_md_file(repo)

        #save files to bucket
        s3 = boto3.resource('s3')
        for f in files:
            with open(repo.repodir+'repodata/'+f, 'rb') as g:
                f_index_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=os.environ['REPO_DIR']+'/repodata/'+f)
                print("Writing file: %s" % (str(f_index_obj)))
                f_index_obj.put(Body=g.read(-1), ACL=get_public())
        f_index_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=os.environ['REPO_DIR']+'/repo_cache')
        print("Writing file: %s" % (str(f_index_obj)))
        f_index_obj.put(Body=str(json.dumps(cache)))

        #Let us clean up
        shutil.rmtree(repo.repodir)
        shutil.rmtree('/tmp/gpgdocs')

        print('METADATA GENERATION COMPLETED')


def check_bucket_file_existance(path):
    """
    checks if file exsist in bucket

    returns bool
    """ 
    s3 = boto3.resource('s3')
    try:
        s3.Object(os.environ['BUCKET_NAME'], path).load()
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        else:
            raise e
    else:
        return True

def get_public():
    """
    If env variable PUBLIC is set to true returns 'public read'
    """
    if os.environ['PUBLIC'] == 'True' :
        acl = 'public-read'
    else:
        acl = 'private'
    return acl

def get_cache(repo):
    """
    Check for cache file
    """
    if check_bucket_file_existance(os.environ['REPO_DIR']+'/repo_cache'):
        print('Repodata cache (%s) found, attempting to write to it' %(os.environ['REPO_DIR']+'/repo_cache'))
        s3 = boto3.client('s3')
        s3.download_file(os.environ['BUCKET_NAME'], os.environ['REPO_DIR']+'/repo_cache', repo.repodir + 'repo_cache')
        with open(repo.repodir + 'repo_cache', 'r') as f:
            cache = json.loads(f.read(-1))
    else:
        print('repodata_cache file doesn\'t exist. Creating new one')
        cache = {}
    return cache

def check_changed_files(repo):
    """
    check if there are any new files in bucket or any deleted files
    """
    print("Checking for changes : %s" % (os.environ['REPO_DIR']))
    cache = get_cache(repo)
    s3 = boto3.resource('s3')
    files = []
    #cycle through all objects ending with .rpm in REPO_DIR and check if they are already in repodata, if not add them
    for obj in s3.Bucket(os.environ['BUCKET_NAME']).objects.filter(Prefix=os.environ['REPO_DIR']):
        if not obj.key.endswith(".rpm"):
            print('skipping %s - not rpm file' %(obj.key))
            continue
        fname = obj.key[len(os.environ['REPO_DIR']):] # '/filename.rpm' - without path
        if fname not in cache:
            s3c = boto3.client('s3')
            #Create path to folder where to download file, if it not yet exists
            prefix = '/'.join(obj.key.split('/')[0:-1])[len(os.environ['REPO_DIR']):]
            if not os.path.exists(repo.repodir+prefix):
                os.makedirs(repo.repodir+prefix)
            #Download file to repodir
            path = repo.repodir + fname
            s3c.download_file(os.environ['BUCKET_NAME'], obj.key, path)
            with open(path, 'rb') as f:
                package = YumPackage(f)
            #add package to repo and cache
            repo.add_package(package)
            cache[fname] = package.checksum
            print('File %s added to metadata'%(obj.key))
        else:
            print('File %s is already in metadata'%(obj.key))
        files.append(obj.key)

    removedPkgs = []
    for f in cache:
        if f.endswith('.rpm') and os.environ['REPO_DIR']+f not in files:
            print('removing ' + os.environ['REPO_DIR']+f)
            repo, _ = remove_pkg(repo, cache, f)
            removedPkgs.append(f)
                
    for removed in removedPkgs:
        del cache[removed]
    return repo, cache

def remove_pkg(repo, cache, key):
    """
    remove package from metadata
    """
    prefix = '/'.join(key.split('/')[0:-1])
    filename = key[len(prefix):]
    if filename in cache:
        repo.remove_package(cache[filename])
        print('%s has been removed from metadata' % (filename))
    else:
        print('Tried to delete %s entry but was not found in cache' % (filename))
    return repo, cache

def sign_md_file(repo):
    '''
    Using gpg password assigned in env variable `GPG_PASS` and key, which's file directory is 
    assigned in env variable `GPG_KEY`
    '''
    gpg = gnupg.GPG(gnupghome='/tmp/gpgdocs')
    s3 = boto3.client('s3')
    s3.download_file(os.environ['BUCKET_NAME'], os.environ['GPG_KEY'], '/tmp/gpgdocs/sec.key')

    with open('/tmp/gpgdocs/sec.key') as stream:
        sec = gpg.import_keys(stream.read(-1))
    print("Key import returned: ")
    print(str(sec.results))
    with open(repo.repodir + 'repodata/repomd.xml', 'rb') as stream:
        signed = gpg.sign_file(stream, passphrase=os.environ['GPG_PASS'], clearsign=True, detach=True, binary=False)

    s3 = boto3.resource('s3')
    sign_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=os.environ['REPO_DIR'] + "/repodata/repomd.xml.asc")
    print('uploading repomd.xml.asc to /repodata')
    sign_obj.put(Body=str(signed), ACL=get_public())