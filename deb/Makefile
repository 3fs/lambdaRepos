ZIPPED_FILES := s3apt.py requirements/gnupg.py # files to compress in root of zip
ZIPPED_DIR   := debian # folders from /requirements to compress to root of zip

all: requires package

help: ## displays this message
	@grep -E '^[a-zA-Z_/%\-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

requires: ## installs required packages
	pip install -t ./requirements -r requirements.txt

package: ## creates zip of code
	zip -j code.zip $(ZIPPED_FILES)
	cd requirements && zip -r ../code.zip $(ZIPPED_DIR)

clean: ## cleans up the repository
	/bin/rm -rf code.zip
	/bin/rm -rf ./requirements