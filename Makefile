.PHONY: verify verify-dev verify-release visual-check

verify:
	uv run python tools/verify_frontend.py

verify-dev:
	uv run python tools/verify_frontend.py --mode dev

verify-release:
	uv run python tools/verify_frontend.py --mode release

visual-check:
	uv run python tools/capture_frontend.py
