ZIPPED_FILES := s3rpm.py gnupg.py # files to compress in root of zip
ZIPPED_DIRS  := pyrpm # folders to compress to zip
all: requires test package

help: ## displays this message
	@grep -E '^[a-zA-Z_/%\-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

requires: ## installs required packages
	pip3 install -t . -r requirements.txt

package: ## creates zip of code
	zip code.zip $(ZIPPED_FILES)
	zip -r code.zip $(ZIPPED_DIRS)

clean: ## cleans up the repository
	/bin/rm -rf code.zip __pycache__ boto3* botocore* concurrent* docutils* dateutil* six* futures* pyrpm* tests* jmespath* python_gnupg* python_dateutil* six.py gnupg.py gnupg.pyc


test: ## runs the tests
	python3.6 s3rpm_test.py