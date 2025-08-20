# Veris Memory CLI Tools

Command-line utilities for testing, debugging, and interacting with the Veris Memory system.

## Tools Overview

### 1. Query Simulator (`query_simulator.py`)

Interactive CLI tool for testing search queries and system performance.

**Features:**
- Interactive query testing with real-time results
- Advanced parameter configuration (search modes, ranking policies, filters)
- Performance benchmarking and analysis
- Session tracking and result export
- Support for both mock and real backends

**Usage:**
```bash
# Interactive mode
python tools/cli/query_simulator.py

# Single query mode
python tools/cli/query_simulator.py --query "python authentication function"

# Benchmark mode
python tools/cli/query_simulator.py --benchmark

# Use real backends instead of mocks
python tools/cli/query_simulator.py --real-backends
```

**Interactive Commands:**
- `search <query>` - Basic search with default settings
- `advanced <query>` - Advanced search with parameter selection
- `benchmark` - Run performance benchmark tests
- `status` - Show system status and health
- `stats` - Show performance statistics
- `backends` - Show backend information
- `policies` - Show available ranking policies
- `session` - Show results from current session
- `export` - Export session results to JSON
- `help` - Show command help
- `quit` - Exit simulator

### 2. Testing Tools (`testing_tools.py`)

Comprehensive testing and validation utilities for system components.

**Features:**
- System validation (backend health, configuration, performance)
- Automated test suite execution
- Load testing with concurrent users
- Detailed result analysis and reporting
- JSON export for CI/CD integration

**Usage:**

**System Validation:**
```bash
# Run complete system validation
python tools/cli/testing_tools.py validate

# Export validation results
python tools/cli/testing_tools.py validate --export validation_results.json
```

**Test Suite Execution:**
```bash
# Run default test suite
python tools/cli/testing_tools.py test

# Export test results
python tools/cli/testing_tools.py test --export test_results.json
```

**Load Testing:**
```bash
# Basic load test (10 users, 5 queries each)
python tools/cli/testing_tools.py load-test

# Custom load test
python tools/cli/testing_tools.py load-test --concurrent-users 20 --queries-per-user 10

# Export load test results
python tools/cli/testing_tools.py load-test --export load_test_results.json
```

## Installation

The CLI tools require the Veris Memory system to be installed. They use the same dependencies as the main system.

### Prerequisites

1. Python 3.8+
2. Veris Memory system installed
3. All system dependencies (see main README.md)

### Setup

```bash
# Ensure you're in the Veris Memory root directory
cd /path/to/veris-memory

# The tools automatically add the src directory to the Python path
# No additional installation required
```

## Integration with Development Workflow

### Pre-Commit Testing

Add to your pre-commit hooks:

```bash
# Run system validation
python tools/cli/testing_tools.py validate

# Run quick test suite
python tools/cli/testing_tools.py test
```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Run System Validation
  run: python tools/cli/testing_tools.py validate --export validation_results.json

- name: Run Test Suite
  run: python tools/cli/testing_tools.py test --export test_results.json

- name: Upload Test Results
  uses: actions/upload-artifact@v2
  with:
    name: test-results
    path: |
      validation_results.json
      test_results.json
```

### Performance Monitoring

Regular performance benchmarking:

```bash
# Daily performance check
python tools/cli/query_simulator.py --benchmark

# Weekly load testing
python tools/cli/testing_tools.py load-test --concurrent-users 50 --queries-per-user 20
```

## Output Examples

### Query Simulator Interactive Session

```
🚀 Initializing Veris Memory Query Simulator...
✅ Query simulator initialized successfully!
📊 Backends: vector, graph, kv
🎯 Ranking policies: default, code_boost, recency

🎮 Interactive Query Simulator
Type 'help' for commands, 'quit' to exit
--------------------------------------------------

🔍 veris-query> search python authentication

🔍 Searching for: 'python authentication'
✅ Found 2 results in 45.2ms
🎯 Search mode: hybrid
🔧 Backends used: vector, graph

1. [code] Score: 0.95
   def process_user_authentication(username: str, password: str) -> bool:
       # Validate user credentials against database...
   Tags: python, authentication, security, function

2. [documentation] Score: 0.92
   API Authentication Guide: Use JWT tokens in the Authorization header...
   Tags: api, jwt, authentication, documentation
```

### System Validation Output

```
🔍 Running System Validation...
----------------------------------------
📊 Validating backend health...
   ✅ 3/3 backends healthy
   ✅ vector: 25.1ms
   ✅ graph: 30.2ms
   ✅ kv: 15.8ms

🔧 Validating dispatcher configuration...
   📦 Registered backends: vector, graph, kv
   🎯 Configuration score: 100%

📋 Validating ranking policies...
   🎯 Available policies: default, code_boost, recency
   📊 Policy validation score: 100%

🔍 Validating filter capabilities...
   🔧 Supported capabilities: 3/3
   ✅ Time Window Filtering
   ✅ Tag Filtering
   ✅ Content Type Filtering

⚡ Validating performance baseline...
   ⏱️  Average response: 42.3ms
   🎯 Success rate: 100.0%
   📊 Performance score: 100.0%

🏆 Overall System Score: 100.0%
```

### Load Test Results

```
🔥 Load Test: 10 users, 5 queries each
------------------------------------------------------------

📊 Load Test Results:
   👥 Users: 10
   📈 Total Queries: 50
   ✅ Successful: 50
   ❌ Failed: 0
   📊 Success Rate: 100.0%
   🔥 Queries/Second: 23.5
   ⏱️  Avg Response: 38.7ms
   📈 95th Percentile: 65.2ms
   ⚡ Min/Max: 15.2ms / 78.9ms
   🕐 Total Test Time: 2127.3ms
```

## Configuration

### Environment Variables

- `VERIS_MEMORY_CONFIG_PATH` - Path to configuration file
- `VERIS_MEMORY_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `VERIS_MEMORY_MOCK_BACKENDS` - Force use of mock backends (true/false)

### Mock vs Real Backends

By default, the CLI tools use mock backends for safe testing. To use real backends:

1. Ensure your system is properly configured
2. Use the `--real-backends` flag for the query simulator
3. Set environment variable: `VERIS_MEMORY_MOCK_BACKENDS=false`

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the Veris Memory root directory
2. **Backend Connection Failures**: Check backend configuration and health
3. **Performance Issues**: Use the validation tools to identify bottlenecks
4. **Test Failures**: Check system logs and validation output

### Debug Mode

Enable debug logging:

```bash
export VERIS_MEMORY_LOG_LEVEL=DEBUG
python tools/cli/query_simulator.py
```

### Getting Help

- Run any tool with `--help` for usage information
- Use the `help` command in interactive mode
- Check system status with validation tools
- Review exported JSON results for detailed analysis

## Contributing

When adding new CLI tools or features:

1. Follow the existing code structure and patterns
2. Add comprehensive help text and documentation
3. Include proper error handling and validation
4. Add example usage and output formats
5. Update this README with new features