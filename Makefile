.PHONY: compile python native demo clean

compile: python native

python:
	python -m compileall -q patchweave

native:
	g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only core/patch_metrics.cpp

demo:
	python -m patchweave --help
