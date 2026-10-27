.PHONY: run test smoke
run:
	python run_demo.py
test:
	python -m pytest -q tests/test_investigator.py
smoke:
	python tests/smoke.py
