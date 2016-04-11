.PHONY: compile python native demo clean

compile: python native

python:
	python -m compileall -q patchweave

native:
