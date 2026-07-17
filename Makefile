.PHONY: verify verify-dev verify-release visual-check quality-baseline quality-checkpoint test-snapshot test-plan test-changed browser-fixture browser-check browser-check-extended accessibility-baseline accessibility-check performance-baseline performance-check postdeploy-check acceptance-verify acceptance-finalize

verify:
	uv run python tools/verify_frontend.py

verify-dev:
	uv run python tools/verify_frontend.py --mode dev

verify-release:
	uv run python tools/verify_frontend.py --mode release

visual-check:
	uv run python tools/capture_frontend.py

quality-baseline:
	uv run python tools/quality_gate.py baseline

quality-checkpoint:
	uv run python tools/quality_gate.py checkpoint

test-snapshot:
	uv run python tools/test_router.py snapshot

test-plan:
	uv run python tools/test_router.py plan

test-changed:
	uv run python tools/test_router.py run

browser-fixture:
	uv run python tools/browser_gate.py --prepare-only

browser-check:
	uv run python tools/browser_gate.py --profile core

browser-check-extended:
	uv run python tools/browser_gate.py --profile extended

accessibility-baseline:
	uv run python tools/accessibility_gate.py baseline

accessibility-check:
	uv run python tools/accessibility_gate.py check

performance-baseline:
	uv run python tools/performance_gate.py baseline

performance-check:
	uv run python tools/performance_gate.py check

postdeploy-check:
	uv run python tools/postdeploy_gate.py check --base-url "$(BASE_URL)" --environment "$(ENVIRONMENT)" --allowed-host "$(ALLOWED_HOST)" --expected-environment "$(ENVIRONMENT)" --expected-release "$(RELEASE)"

acceptance-verify:
	uv run python tools/acceptance_gate.py verify --task "$(TASK)"

acceptance-finalize:
	uv run python tools/acceptance_gate.py finalize --run-dir "$(RUN_DIR)" --review "$(REVIEW)"
