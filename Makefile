.PHONY: install test lint generate-examples clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

generate-examples:
	python -m terragen generate --answers examples/answers-aws.yaml --out tmp-gen/aws --force
	python -m terragen generate --answers examples/answers-gcp.yaml --out tmp-gen/gcp --force
	python -m terragen generate --answers examples/answers-azure.yaml --out tmp-gen/azure --force
	python -m terragen generate --answers examples/answers-aws-secure.yaml --out tmp-gen/aws-secure --force

validate-examples: generate-examples
	@for d in aws gcp azure aws-secure; do \
	  (cd tmp-gen/$$d && terraform init -backend=false -input=false && terraform validate); \
	done

clean:
	rm -rf tmp-gen dist build *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
