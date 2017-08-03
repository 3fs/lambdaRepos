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
        os.environ['REPO_DIR'] = 'test/repo/'
        os.environ['GPG_KEY'] = ''
        os.environ['PUBLIC'] = 'True'

    def test_remove_pkg(self):
        repo = YumRepository('test/repo/')
        cachef = open(repo.repodir + 'repo_cache', 'r')
        cache = json.loads(cachef.read(-1))
        repo, cache = s3rpm.remove_pkg(repo, cache, ('/pkgname-0.3.7-x86_64.rpm'))
        cachef.close()
        assert len(list(repo.packages())) == 0
        assert cache == {}

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
        cache = '{"pkgname":"ID"}'
        m = mock_open(read_data=cache)
        check_mock.return_value = True

        with patch('s3rpm.open', m):
            cachenew = s3rpm.get_cache(repo)
        assert json.loads(cache) == cachenew
        
        check_mock.return_value = False

        cachenew = s3rpm.get_cache(repo)
        assert cachenew == {}

    @patch('s3rpm.get_cache')
    @patch('s3rpm.YumRepository')
    @patch('s3rpm.boto3')
    def test_hander(self, s3_mock, repo_mock, cache_mock):
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
