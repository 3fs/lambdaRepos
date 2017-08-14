import unittest
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch
from unittest.mock import PropertyMock

import s3rpm

import botocore
import os
import json
import shutil

class SubFunctionsTest(unittest.TestCase):  

    def setUp(self):
        os.environ['BUCKET_NAME'] = 'bucket'
        os.environ['REPO_DIR'] = 'test_s3rpm'
        os.environ['GPG_KEY'] = ''
        os.environ['PUBLIC'] = 'True'
        os.environ['GPG_PASS']='123'
    
    def tearDown(self):
        if os.path.exists('test_s3rpm'):
            shutil.rmtree('test_s3rpm')

    def test_public_private(self):
        os.environ['PUBLIC'] = 'True'
        self.assertEqual(s3rpm.get_public(), 'public-read')

        os.environ['PUBLIC'] = ''
        self.assertEqual(s3rpm.get_public(), 'private')

        os.environ['PUBLIC'] = 'False'
        self.assertEqual(s3rpm.get_public(), 'private')
    

    @patch('s3rpm.boto3')
    def test_file_existance(self, s3_mock):
        ret = s3rpm.check_bucket_file_existance('path')
        self.assertEqual(ret, True)
        s3_mock.resource().Object.assert_called_with("bucket", "path")
        s3_mock.resource().Object().load.assert_called_with()

        #404 error
        p = PropertyMock(side_effect=botocore.exceptions.ClientError({'Error':{'Code': '404','Message':'no msg'}}, 'aa'))
        s3_mock.resource().Object().load = p

        ret = s3rpm.check_bucket_file_existance('path')
        self.assertEqual(ret, False)
        #non404 error
        p = PropertyMock(side_effect=botocore.exceptions.ClientError({'Error':{'Code': '403','Message':'no msg'}}, 'aa'))
        s3_mock.resource().Object().load = p

        with self.assertRaises(botocore.exceptions.ClientError):
            s3rpm.check_bucket_file_existance('path')
            
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.boto3')
    @patch('s3rpm.check_bucket_file_existance')
    def test_cache(self, check_mock, s3_mock, yum_mock):
        yum_mock = MagicMock(repodir='test_s3rpm/')
        cache = '{"pkgname" : "ID"}'
        repo = yum_mock
        m = mock_open(read_data=cache)
        check_mock.return_value = True

        with patch('s3rpm.open', m):
            cachenew = s3rpm.get_cache(repo, os.environ['REPO_DIR'])
        s3_mock.client().download_file.assert_called_with('bucket', 'test_s3rpm/repo_cache', 'test_s3rpm/repo_cache')
        self.assertEqual(json.loads(cache), cachenew)
        
        check_mock.return_value = False

        cachenew = s3rpm.get_cache(repo,os.environ['REPO_DIR'])
        self.assertEqual(cachenew, {})

    @patch('s3rpm.YumRepository')
    @patch('s3rpm.YumPackage')
    @patch('s3rpm.get_cache')
    @patch('s3rpm.boto3')
    def test_new_files(self, s3_mock, cache_mock, yump_mock, yum_mock):
        
        cache_mock.return_value = {"/pkgname-0.3.7-x86_64.rpm": "test_id1"}
        yum_mock = MagicMock(repodir='test_s3rpm/')
        repo = yum_mock
        yump_mock.return_value = MagicMock(checksum='test_id2')
        cache = {"/pkgname-0.3.7-x86_64.rpm": "test_id1", "/pkgname-0.3.8-x86_64.rpm": "test_id2"}
        

        s3_mock.resource().Bucket().objects.filter.return_value = [MagicMock(key='test.file'),MagicMock(key='test_s3rpm/pkgname-0.3.8-x86_64.rpm'), MagicMock(key='test_s3rpm/pkgname-0.3.7-x86_64.rpm')]
        m = mock_open(read_data='')
        with patch('s3rpm.open', m):
            reponew, cachenew = s3rpm.check_changed_files(repo, os.environ['REPO_DIR'])

        self.assertEqual(cache, cachenew)
        self.assertEqual(yum_mock.add_package.call_count, 1)

    
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.get_cache')
    @patch('s3rpm.boto3')
    def test_delete_files(self, s3_mock, cache_mock, yum_mock):
        cache_mock.return_value = {"/pkgname-0.3.7-x86_64.rpm": "test_id1"}
        yum_mock = MagicMock(repodir='test_s3rpm/')
        repo = yum_mock
        cache = {}

        s3_mock.resource().Bucket().objects.filter.return_value = [MagicMock(key='test.file')]
        _, cachenew = s3rpm.check_changed_files(repo, os.environ['REPO_DIR'])
        self.assertEqual(cache, cachenew)
        self.assertEqual(yum_mock.remove_package.call_count, 1)
        
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.gnupg')
    @patch('s3rpm.boto3')
    def test_gpg(self, s3_mock, gpg_mock, yum_mock):
        os.environ['GPG_KEY'] = 'KeyNowExists'
        m = mock_open()
        repo = yum_mock()
        with patch('s3rpm.open', m):
            s3rpm.sign_md_file(repo, os.environ['REPO_DIR'])
            gpg_mock.GPG().sign_file.assert_called_with(s3rpm.open(), binary=False, clearsign=True, detach=True, passphrase='123')
        s3_mock.resource().Object().put.assert_called_with(ACL='public-read', Body=str(gpg_mock.GPG().sign_file()))
    
    def test_create_dir(self):
        ret = s3rpm.create_new_dir_if_not_exist('test_s3rpm/testfolder')
        self.assertEqual(True, ret)
        ret = s3rpm.create_new_dir_if_not_exist('test_s3rpm/testfolder')
        self.assertEqual(False, ret)


class HandlerTest(unittest.TestCase):
    def setUp(self):
        os.environ['BUCKET_NAME'] = 'bucket'
        os.environ['REPO_DIR'] = 'test_s3rpm'
        os.environ['GPG_KEY'] = ''
        os.environ['PUBLIC'] = 'True'
        os.environ['GPG_PASS']='123'
        self.m = mock_open(read_data='')

    def tearDown(self):
        if os.path.exists('test_s3rpm'):
            shutil.rmtree('test_s3rpm')
    @patch('s3rpm.get_cache')
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.boto3')
    def test_defined_repodir(self, s3_mock, yum_mock, cache_mock, ):
        cache_mock.return_value = {"pkgname":"ID"}

        yum_mock.return_value = MagicMock(repodir='test_s3rpm/')
        with patch('s3rpm.open', self.m):
            s3rpm.lambda_handler(S3_EVENT, {})
        self.assertEqual(len(s3_mock.resource().Object().put.mock_calls), 5)
        self.assertEqual(os.environ['REPO_DIR'],'test_s3rpm')
    
    @patch('s3rpm.gnupg')
    @patch('s3rpm.shutil')
    @patch('s3rpm.get_cache')
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.boto3')
    def test_gpg_from_handler(self, s3_mock, yum_mock, cache_mock, sh_mock, gpg_mock):
        cache_mock.return_value = {"pkgname":"ID"}

        os.environ['GPG_KEY'] = 'KeyNowExists'
        check = MagicMock()
        check.return_value = False
        yum_mock.return_value = MagicMock(repodir='test_s3rpm/testrepo/')
        with patch('s3rpm.open', self.m):
            with patch('s3rpm.check_bucket_file_existance', check):
                s3rpm.lambda_handler(S3_EVENT, {})
                gpg_mock.GPG().sign_file.assert_called_with(s3rpm.open(), binary=False, clearsign=True, detach=True, passphrase='123')
        assert os.path.exists('test_s3rpm/testrepo/') == True

    @patch('s3rpm.boto3')
    def test_bad_bucket_name(self, s3_mock):
        os.environ['BUCKET_NAME'] = 'iamfakebucket'
        s3rpm.lambda_handler(S3_EVENT, {})
        s3_mock.client.assert_called_with('s3')
        self.assertEqual(len(s3_mock.resource().Object().put.mock_calls), 0)
S3_EVENT = {"Records":[{"s3": {"object": {"key": "test_s3rpm/repo/pkgname-0.3.8-x86_64.rpm",},"bucket": {"name": "bucket",},},"eventName": "ObjectCreated:Put"}]}
if __name__ == '__main__':
    unittest.main()
