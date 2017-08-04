import unittest
from pyrpm.tools.createrepo import YumRepository
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch
import os
import s3rpm
import json

class S3AptTest(unittest.TestCase):  
    def setUp(self):
        os.environ['BUCKET_NAME'] = 'bucket'
        os.environ['REPO_DIR'] = 'test/repo'
        os.environ['GPG_KEY'] = ''
        os.environ['PUBLIC'] = 'True'

    def test_public_private(self):
        os.environ['PUBLIC'] = 'True'
        assert s3rpm.get_public() == 'public-read'

        os.environ['PUBLIC'] = ''
        assert s3rpm.get_public() == 'private'

        os.environ['PUBLIC'] = 'False'
        assert s3rpm.get_public() == 'private'
    
    @patch('s3rpm.boto3')
    def test_file_existance(self, s3_mock):
        ret = s3rpm.check_bucket_file_existance('path')
        assert ret == True
        s3_mock.resource().Object.assert_called_with("bucket", "path")
        s3_mock.resource().Object().load.assert_called_with()

    @patch('s3rpm.boto3')
    @patch('s3rpm.check_bucket_file_existance')
    def test_cache(self, check_mock, s3_mock):
        repo = YumRepository('test/repo/')
        cache = '{"/pkgname":"ID"}'
        m = mock_open(read_data=cache)
        check_mock.return_value = True

        with patch('s3rpm.open', m):
            cachenew = s3rpm.get_cache(repo)
        assert json.loads(cache) == cachenew
        
        check_mock.return_value = False

        cachenew = s3rpm.get_cache(repo)
        assert cachenew == {}


    @patch('s3rpm.get_cache')
    @patch('s3rpm.boto3')
    def test_new_files(self, s3_mock, cache_mock):
        cache_mock.return_value = {"/pkgname-0.3.7-x86_64.rpm": "7cd368172d218ed2001ad7306ff74c727f0b1d7bfa5433d9b265e7830bf60184"}
        repo = YumRepository('test/repo/')
        repo.read()
        cache = {"/pkgname-0.3.7-x86_64.rpm": "7cd368172d218ed2001ad7306ff74c727f0b1d7bfa5433d9b265e7830bf60184", "/pkgname-0.3.8-x86_64.rpm": "edcdbd077673a759585b1ebd4589d900c230a63e2c91c787861bcdcec9004707"}

        s3_mock.resource().Bucket().objects.filter.return_value = [MagicMock(key='test.file'),MagicMock(key='test/repo/pkgname-0.3.8-x86_64.rpm'), MagicMock(key='test/repo/pkgname-0.3.7-x86_64.rpm')]
        reponew, cachenew = s3rpm.check_changed_files(repo)

        assert cache == cachenew
        self.assertEqual(len(list(reponew.packages())), 2)
    
    @patch('s3rpm.get_cache')
    @patch('s3rpm.boto3')
    def test_delete_files(self, s3_mock, cache_mock):
        cache_mock.return_value = {"/pkgname-0.3.7-x86_64.rpm": "7cd368172d218ed2001ad7306ff74c727f0b1d7bfa5433d9b265e7830bf60184"}
        repo = YumRepository('test/repo/')
        cache = {}

        s3_mock.resource().Bucket().objects.filter.return_value = [MagicMock(key='test.file')]
        reponew, cachenew = s3rpm.check_changed_files(repo)
        assert cache == cachenew
        self.assertEqual(len(list(reponew.packages())), 0)

    @patch('s3rpm.shutil')
    @patch('s3rpm.get_cache')
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.boto3')
    def test_hander(self, s3_mock, repo_mock, cache_mock, shutil_mock):
        cache_mock.return_value = {"pkgname":"ID"}
        repo_mock.return_value = YumRepository('test/repo/')   
        m = mock_open(read_data='')
        with patch('s3rpm.open', m):
            s3rpm.lambda_handler(S3_EVENT, {})
        self.assertEqual(len(s3_mock.resource().Object().put.mock_calls), 5)

    
S3_EVENT = {"Records":[{"s3": {"object": {"key": "test/repo/pkgname-0.3.8-x86_64.rpm",},"bucket": {"name": "bucket",},},"eventName": "ObjectCreated:Put",}]}
if __name__ == '__main__':
    unittest.main()

def createrepo():
    repo = YumRepository('test/repo/')
    repo.add_package(YumPackage(open('test/repo/pkgname-0.3.7-x86_64.rpm', 'rb')))
    repo.save()
