from __future__ import print_function
from time import gmtime, strftime
import urllib
import boto3
import botocore
import tempfile
import tarfile
import debian.arfile
import hashlib
import re
import sys
import os
import gnupg

def lambda_handler(event, context):
    print('Starting lambda function')
    #Get bucket and key info
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key']).decode('utf8')

    if bucket == os.environ['BUCKET_NAME'] and key.endswith(".deb"):
        #Build packages file
        if event['Records'][0]['eventName'].startswith('ObjectCreated'):
            s3 = boto3.resource('s3')
            deb_obj = s3.Object(bucket_name=bucket, key=key)
            print("S3 Notification of new key. Ensuring cached control data exists: %s" % (str(deb_obj)))
            get_cached_control_data(deb_obj)
    
        prefix = "/".join(key.split('/')[0:-1]) + '/'
        #Update packages file
        rebuild_package_index(prefix)

        #Build Release file
        build_release_file(prefix)
    
        #Sign Release file
        if os.environ['GPG_KEY']!='':
            sign_release_file(prefix)


def get_cached_control_data(deb_obj):
    #gets debian control data
    s3 = boto3.resource('s3')
    etag = deb_obj.e_tag.strip('"')

    cache_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=os.environ['CACHE_PREFIX'] + '/' + etag)
    exists = True
    try:
        control_data = cache_obj.get()['Body'].read()
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            exists = False
        else:
            raise(e)

    if not exists:
        control_data = read_control_data(deb_obj)
        cache_obj.put(Body=control_data)

    return control_data

def read_control_data(deb_obj):
    fd, tmp = tempfile.mkstemp()
    fh = os.fdopen(fd, "wb")
    s3fh = deb_obj.get()['Body']
    size = 1024*1024
    while True:
        dat = s3fh.read(size)
        fh.write(dat)
        if len(dat) < size:
            break
    fh.close()

    try:
        ctrl = get_control_data(tmp)
        pkg_rec = format_package_record(ctrl, tmp)
        return pkg_rec
    finally:
        os.remove(tmp)

def get_control_data(debfile):
    ar = debian.arfile.ArFile(debfile)

    control_fh = ar.getmember('control.tar.gz')

    tar_file = tarfile.open(fileobj=control_fh, mode='r:gz')

    # control file can be named different things
    control_file_name = [x for x in tar_file.getmembers() if x.name in ['control', './control']][0]

    control_data = tar_file.extractfile(control_file_name).read().strip()
    # Strip out control fields with blank values.  This tries to allow folded
    # and multiline fields to pass through.  See the debian policy manual for
    # more info on folded and multiline fields.
    # https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-binarycontrolfiles
    lines = control_data.strip().split("\n")
    filtered = []
    for line in lines:
        # see if simple field
        if re.search(r"^\w[\w\d_-]+\s*:", line):
            k, v = line.split(':', 1)
            if v.strip() != "":
                filtered.append(line)
        else:
            # otherwise folded or multiline, just pass it through
            filtered.append(line)

    return "\n".join(filtered)

def format_package_record(ctrl, fname):
    pkgrec = ctrl.strip().split("\n")

    stat = os.stat(fname)
    pkgrec.append("Size: %d" % (stat.st_size))

    md5, sha1, sha256 = checksums(fname)
    pkgrec.append("MD5sum: %s" % (md5))
    pkgrec.append("SHA1: %s" % (sha1))
    pkgrec.append("SHA256: %s" % (sha256))

    return "\n".join(pkgrec)

def checksums(fname):

    fh = open(fname, "rb")

    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()

    size = 1024 * 1024
    while True:
        dat = fh.read(size)
        md5.update(dat)
        sha1.update(dat)
        sha256.update(dat)
        if len(dat) < size:
            break

    fh.close()

    return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()

def rebuild_package_index(prefix):
    # Get all .deb keys in directory
    # Get the cache entry
    # build package file
    deb_names = []
    deb_objs = []

    print("REBUILDING PACKAGE INDEX: %s" % (prefix))
    s3 = boto3.resource('s3')
    for obj in s3.Bucket(os.environ['BUCKET_NAME']).objects.filter(Prefix=prefix):
        if not obj.key.endswith(".deb"):
            continue
        deb_objs.append(obj)
        deb_names.append(obj.key.split('/')[-1])

    if not len(deb_objs):
        print("NOT BUILDING EMPTY PACKAGE INDEX")
        return

    # See if we need to rebuild the package index
    metadata_pkghash = get_package_index_hash(prefix)
    calcd_pkghash = calc_package_index_hash(deb_names)
    print("calcd_pkghash=%s, metadata_pkghash=%s" % (calcd_pkghash, metadata_pkghash))
    if metadata_pkghash == calcd_pkghash:
        print("PACKAGE INDEX ALREADY UP TO DATE")
        return

    pkginfos = []
    for obj in deb_objs:
        print(obj.key)

        pkginfo = get_cached_control_data(obj)
        if obj.key.startswith(prefix):
            filename = obj.key[len(prefix):]
            pkginfo = pkginfo + "\n%s\n" % ("Filename: %s" % filename)
        else:
            pkginfo = pkginfo + "\n%s\n" % ("Filename: %s" % obj.key)

        pkginfos.append(pkginfo)

    package_index_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=prefix + "Packages")
    print("Writing package index: %s" % (str(package_index_obj)))
    if os.environ['PUBLIC'] == 'True' :
        acl = 'public-read'
    else:
        acl = 'private'
    package_index_obj.put(Body="\n".join(sorted(pkginfos)), Metadata={'packages-hash': calcd_pkghash}, ACL=acl)

    print("DONE REBUILDING PACKAGE INDEX")

def calc_package_index_hash(deb_names):
    """
    Calculates a hash of all the given deb file names. This is deterministic so
    we can use it for short-circuiting.
    """

    md5 = hashlib.md5()
    md5.update("\n".join(sorted(deb_names)))
    return md5.hexdigest()

def get_package_index_hash(prefix):
    """
    Returns the md5 hash of the names of all the packages in the index. This can be used
    to detect if all the packages are represented without having to load a control data cache
    file for each package.can be used
    to detect if all the packages are represented without having to load a control data cache
    file for each package.
    """
    s3 = boto3.resource('s3')
    try:
        print("looking for existing Packages file: %sPackages" % prefix)
        package_index_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=prefix + 'Packages')
        return package_index_obj.metadata.get('packages-hash', None)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise(e)

def build_release_file(prefix):
    """
    gets info from Package, get the sums and puts them into file

    Releasefile layout:
    '''
    Date: <Day of the week>, DD Mmm YYYY HH:MM:SS UTC
    MD5sum:
    <md5sum>  <(17 - length of size) spaces> <size> Packages
    SHA1:
    <sha1>  <(17 - length of size) spaces> <size> Packages
    SHA256:
    <sha256>  <(17 - length of size) spaces> <size> Packages
    '''
    """
    s3 = boto3.client('s3')
    release_file = ""
    s3.download_file(os.environ['BUCKET_NAME'], prefix + "Packages", '/tmp/Packages')
    md5, sha1, sha256 = checksums("/tmp/Packages")

    date = 'Date: ' + strftime("%a, %d %b %Y %X UTC", gmtime())
    stat = os.stat("/tmp/Packages")

    release_file += (date + '\nMD5sum:\n ' + md5)
    for i in range(0,17-len(str(stat.st_size))):
        release_file +=(' ')
    release_file +=("%d Packages\nSHA1:\n %s" %(stat.st_size, sha1))
    for i in range(0,17-len(str(stat.st_size))):
        release_file +=(' ')
    release_file +=("%d Packages\nSHA256:\n %s" %(stat.st_size, sha256 ))
    for i in range(0,17-len(str(stat.st_size))):
        release_file +=(' ')
    release_file +=('%d Packages' % stat.st_size)

    s3 = boto3.resource('s3')

    if os.environ['PUBLIC'] == 'True' :
        acl = 'public-read'
    else:
        acl = 'private'

    release_index_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=prefix + "Release")
    print("Writing Release file: %s" % (str(release_index_obj)))
    release_index_obj.put(Body=release_file, ACL=acl)

def sign_release_file(prefix):
    '''
    Using gpg password assigned in env variable `GPG_PASS` and key, which's file directory is 
    assigned in env variable `GPG_KEY`
    '''
    gpg = gnupg.GPG(gnupghome='/tmp/gpgdocs')
    s3 = boto3.client('s3')
    s3.download_file(os.environ['BUCKET_NAME'], os.environ['GPG_KEY'], '/tmp/gpgdocs/sec.key')
    s3.download_file(os.environ['BUCKET_NAME'], prefix + 'Release', '/tmp/gpgdocs/Release')

    with open('/tmp/gpgdocs/sec.key') as stream:
        sec = gpg.import_keys(stream.read(-1))
    print("Key import returned: ")
    print(sec.results)
    with open('/tmp/gpgdocs/Release') as stream:
        # do not call passphrase=.. if password is not set as it causes bad sign
        if os.environ['GPG_PASS'] == '':
            signed = gpg.sign_file(stream, clearsign=True, detach=True, binary=False)
        else:
            signed = gpg.sign_file(stream, passphrase=os.environ['GPG_PASS'], clearsign=True, detach=True, binary=False)

    if os.environ['PUBLIC'] == 'True' :
        acl = 'public-read'
    else:
        acl = 'private'
    s3 = boto3.resource('s3')
    sign_obj = s3.Object(bucket_name=os.environ['BUCKET_NAME'], key=prefix + "Release.gpg")
    sign_obj.put(Body=str(signed), ACL=acl)
