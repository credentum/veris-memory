# CI Container Integration with Claude Code Review

## Overview

This document describes the integration between the Claude Code Review workflow and the containerized CI environment.

## Container Details

- **Image**: `ghcr.io/credentum/veris-memory-ci:latest`
- **Base**: Python 3.11-slim
- **Build Workflow**: `.github/workflows/build-ci-container.yml`
- **Dockerfile**: `dockerfiles/Dockerfile.ci`

## Performance Improvements

The containerized CI environment provides:
- **94.6% reduction** in CI setup time (from ~185s to ~10s)
- Pre-installed dependencies (no pip install during CI)
- Pre-compiled Python files for faster startup
- Pre-created directories needed by tests

## Claude Code Review Integration

### How It Works

1. **PR Trigger**: When a PR is opened or updated, the Claude Code Review workflow starts
2. **Container Pull**: GitHub Actions pulls the pre-built CI container
3. **Code Review**: Claude runs within the container with access to all tools:
   - Test execution (`./scripts/run-tests.sh ci`)
   - Pre-commit hooks
   - Coverage analysis
   - Schema validation
4. **Results**: Review is posted as YAML-formatted comment with:
   - Coverage metrics
   - Blocking issues
   - Warnings and nits
   - Automated follow-up issues

### Key Features

- **Sticky Comments**: Reviews update in place rather than creating new comments
- **Format Correction**: Automatic YAML format validation and correction
- **Status Checks**: Creates `ARC-Reviewer` status check on commits
- **Coverage Enforcement**: Blocks PRs below 30% coverage baseline
- **Automation**: Creates follow-up issues after PR merge

## Testing the Integration

To verify the CI container integration:

```bash
# 1. Create a test branch
git checkout -b test/ci-integration

# 2. Make a change (e.g., add a test file)
echo "# Test" > tests/test_ci.py

# 3. Commit and push
git add tests/test_ci.py
git commit -m "test: Verify CI container integration"
git push -u origin test/ci-integration

# 4. Create PR
gh pr create --title "Test CI Container" --body "Testing CI container integration"
```

## Monitoring

Check workflow execution:
- Go to Actions tab in GitHub
- Look for "Claude Code Review" workflow
- Verify container is pulled successfully
- Check that tests run within container
- Confirm review comment is posted

## Troubleshooting

### Container Pull Failures

If container pull fails:
1. Check GitHub Container Registry permissions
2. Verify `GITHUB_TOKEN` has `packages: read` permission
3. Ensure container was built successfully

### Test Execution Issues

If tests fail in container:
1. Check that all dependencies are in `requirements-dev.txt`
2. Verify directories exist (created in Dockerfile)
3. Review test logs for missing modules

### Coverage Problems

If coverage is reported as 0%:
1. Ensure `coverage.json` is generated
2. Check `./scripts/run-tests.sh ci` script
3. Verify pytest-cov is installed in container

## Recent Updates

- **PR #133**: Initial containerized CI implementation
- **PR #134**: Enabled container and restored coverage enforcement
- **PR #135**: Adjusted coverage baseline to 30%

## Benefits

1. **Speed**: 95% faster CI workflows
2. **Consistency**: Same environment for all PRs
3. **Reliability**: No dependency installation failures
4. **Maintainability**: Single Dockerfile to update

## Future Improvements

- [ ] Add caching for test results
- [ ] Implement parallel test execution
- [ ] Add security scanning to container build
- [ ] Create multi-arch builds (arm64 support)