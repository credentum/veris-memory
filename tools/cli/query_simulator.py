#!/usr/bin/env python3
"""
CLI Query Simulator for Veris Memory System.

Interactive command-line tool for testing search queries, ranking policies,
filtering configurations, and system performance. Provides realistic
testing scenarios and debugging capabilities.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_dispatcher import QueryDispatcher, SearchMode, DispatchPolicy
from interfaces.memory_result import MemoryResult, ContentType, ResultSource
from storage.mock_backends import MockVectorBackend, MockGraphBackend, MockKVBackend
from filters.pre_filter import PreFilterEngine, FilterCriteria, FilterOperator
from ranking.ranking_policy import RankingPolicyEngine


class QuerySimulator:
    """Interactive CLI query simulator for testing Veris Memory system."""
    
    def __init__(self, use_mock_backends: bool = True):
        """Initialize the query simulator."""
        self.dispatcher = None
        self.use_mock_backends = use_mock_backends
        self.session_results: List[Dict[str, Any]] = []
        self.performance_stats: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize the query dispatcher and backends."""
        print("🚀 Initializing Veris Memory Query Simulator...")
        
        # Initialize dispatcher
        self.dispatcher = QueryDispatcher()
        
        if self.use_mock_backends:
            # Use mock backends for testing
            vector_backend = MockVectorBackend()
            graph_backend = MockGraphBackend()
            kv_backend = MockKVBackend()
            
            # Populate with sample data
            await self._populate_sample_data(vector_backend, graph_backend, kv_backend)
        else:
            # Use real backends (would need configuration)
            from storage.vector_backend import VectorBackend
            from storage.graph_backend import GraphBackend
            from storage.kv_backend import KVBackend
            
            vector_backend = VectorBackend()
            graph_backend = GraphBackend()
            kv_backend = KVBackend()
        
        # Register backends
        self.dispatcher.register_backend("vector", vector_backend)
        self.dispatcher.register_backend("graph", graph_backend) 
        self.dispatcher.register_backend("kv", kv_backend)
        
        print("✅ Query simulator initialized successfully!")
        print(f"📊 Backends: {', '.join(self.dispatcher.list_backends())}")
        print(f"🎯 Ranking policies: {', '.join(self.dispatcher.get_available_ranking_policies())}")
        print()
    
    async def _populate_sample_data(self, vector_backend, graph_backend, kv_backend):
        """Populate mock backends with realistic sample data."""
        sample_contexts = [
            # Code examples
            MemoryResult(
                id="code_1",
                text="def process_user_authentication(username: str, password: str) -> bool:\n    # Validate user credentials against database\n    return auth_service.validate(username, password)",
                type=ContentType.CODE,
                score=0.95,
                source=ResultSource.VECTOR,
                timestamp=datetime.now(timezone.utc),
                tags=["python", "authentication", "security", "function"],
                metadata={"language": "python", "complexity": "medium"}
            ),
            MemoryResult(
                id="code_2", 
                text="async function fetchUserData(userId) {\n  const response = await fetch(`/api/users/${userId}`);\n  return response.json();\n}",
                type=ContentType.CODE,
                score=0.88,
                source=ResultSource.VECTOR,
                timestamp=datetime.now(timezone.utc),
                tags=["javascript", "async", "api", "fetch"],
                metadata={"language": "javascript", "complexity": "simple"}
            ),
            # Documentation
            MemoryResult(
                id="docs_1",
                text="API Authentication Guide: Use JWT tokens in the Authorization header. Format: 'Bearer <token>'. Tokens expire after 24 hours.",
                type=ContentType.DOCUMENTATION,
                score=0.92,
                source=ResultSource.GRAPH,
                timestamp=datetime.now(timezone.utc),
                tags=["api", "jwt", "authentication", "documentation"],
                metadata={"section": "security", "type": "guide"}
            ),
            # Configuration
            MemoryResult(
                id="config_1",
                text="database:\n  host: localhost\n  port: 5432\n  name: veris_memory\n  pool_size: 20",
                type=ContentType.CONFIGURATION,
                score=0.85,
                source=ResultSource.KV,
                timestamp=datetime.now(timezone.utc),
                tags=["database", "config", "postgresql"],
                metadata={"format": "yaml", "component": "database"}
            ),
            # Design documents
            MemoryResult(
                id="design_1",
                text="System Architecture: The Veris Memory system uses a hybrid storage approach combining vector embeddings for semantic search with graph databases for relationship modeling.",
                type=ContentType.DESIGN,
                score=0.90,
                source=ResultSource.GRAPH,
                timestamp=datetime.now(timezone.utc),
                tags=["architecture", "design", "storage", "hybrid"],
                metadata={"document_type": "architecture", "status": "approved"}
            )
        ]
        
        # Store in backends
        for context in sample_contexts:
            if context.source == ResultSource.VECTOR:
                await vector_backend.store_context(context)
            elif context.source == ResultSource.GRAPH:
                await graph_backend.store_context(context)
            elif context.source == ResultSource.KV:
                await kv_backend.store_context(context)
    
    async def run_interactive_mode(self):
        """Run interactive query simulation mode."""
        print("🎮 Interactive Query Simulator")
        print("Type 'help' for commands, 'quit' to exit")
        print("-" * 50)
        
        while True:
            try:
                command = input("\n🔍 veris-query> ").strip()
                
                if not command:
                    continue
                elif command.lower() in ['quit', 'exit', 'q']:
                    break
                elif command.lower() == 'help':
                    self._show_help()
                elif command.lower() == 'status':
                    await self._show_status()
                elif command.lower() == 'stats':
                    self._show_performance_stats()
                elif command.lower() == 'backends':
                    await self._show_backend_info()
                elif command.lower() == 'policies':
                    self._show_ranking_policies()
                elif command.lower().startswith('search '):
                    query = command[7:]  # Remove 'search '
                    await self._run_search(query)
                elif command.lower().startswith('advanced '):
                    query = command[9:]  # Remove 'advanced '
                    await self._run_advanced_search(query)
                elif command.lower() == 'benchmark':
                    await self._run_benchmark()
                elif command.lower() == 'session':
                    self._show_session_results()
                elif command.lower() == 'export':
                    self._export_session_results()
                else:
                    print(f"❌ Unknown command: {command}")
                    print("Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def _show_help(self):
        """Show available commands."""
        help_text = """
🎮 Available Commands:

Search Commands:
  search <query>              - Basic search with default settings
  advanced <query>            - Advanced search with interactive parameters
  benchmark                   - Run performance benchmark tests

System Commands:
  status                      - Show system status and health
  stats                       - Show performance statistics
  backends                    - Show backend information
  policies                    - Show available ranking policies

Session Commands:
  session                     - Show results from current session
  export                      - Export session results to JSON file

General:
  help                        - Show this help message
  quit/exit/q                 - Exit the simulator

Examples:
  search python authentication
  advanced user management system
  """
        print(help_text)
    
    async def _show_status(self):
        """Show system status and health."""
        print("\n📊 System Status:")
        print("-" * 30)
        
        # Backend health
        health_results = await self.dispatcher.health_check_all_backends()
        for backend_name, health in health_results.items():
            status_emoji = "✅" if health["status"] == "healthy" else "❌"
            print(f"{status_emoji} {backend_name}: {health['status']} ({health['response_time_ms']:.1f}ms)")
        
        # System capabilities
        capabilities = self.dispatcher.get_filter_capabilities()
        print(f"\n🔧 Filter Capabilities:")
        for capability, supported in capabilities.items():
            emoji = "✅" if supported else "❌"
            print(f"{emoji} {capability.replace('_', ' ').title()}")
        
        # Performance stats
        perf_stats = self.dispatcher.get_performance_stats()
        print(f"\n⚡ Performance:")
        print(f"Registered backends: {len(perf_stats['registered_backends'])}")
        print(f"Total queries: {len(self.session_results)}")
    
    def _show_performance_stats(self):
        """Show detailed performance statistics."""
        if not self.session_results:
            print("📊 No performance data available yet. Run some queries first!")
            return
        
        print("\n📊 Performance Statistics:")
        print("-" * 40)
        
        # Response time stats
        response_times = [r['response_time_ms'] for r in self.session_results]
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"⏱️  Response Times:")
        print(f"   Average: {avg_time:.1f}ms")
        print(f"   Min: {min_time:.1f}ms")
        print(f"   Max: {max_time:.1f}ms")
        
        # Search mode usage
        search_modes = {}
        for result in self.session_results:
            mode = result.get('search_mode_used', 'unknown')
            search_modes[mode] = search_modes.get(mode, 0) + 1
        
        print(f"\n🎯 Search Mode Usage:")
        for mode, count in search_modes.items():
            print(f"   {mode}: {count} queries")
        
        # Backend usage
        backend_usage = {}
        for result in self.session_results:
            for backend in result.get('backends_used', []):
                backend_usage[backend] = backend_usage.get(backend, 0) + 1
        
        print(f"\n🔧 Backend Usage:")
        for backend, count in backend_usage.items():
            print(f"   {backend}: {count} queries")
    
    async def _show_backend_info(self):
        """Show detailed backend information."""
        print("\n🔧 Backend Information:")
        print("-" * 30)
        
        backends = self.dispatcher.list_backends()
        for backend_name in backends:
            print(f"\n📦 {backend_name.upper()} Backend:")
            
            # Health check
            health = await self.dispatcher.health_check_all_backends()
            backend_health = health.get(backend_name, {"status": "unknown", "response_time_ms": 0})
            status_emoji = "✅" if backend_health["status"] == "healthy" else "❌"
            print(f"   Status: {status_emoji} {backend_health['status']}")
            print(f"   Response Time: {backend_health['response_time_ms']:.1f}ms")
    
    def _show_ranking_policies(self):
        """Show available ranking policies and their details."""
        print("\n🎯 Ranking Policies:")
        print("-" * 25)
        
        policies = self.dispatcher.get_available_ranking_policies()
        for policy_name in policies:
            policy_info = self.dispatcher.get_ranking_policy_info(policy_name)
            print(f"\n📋 {policy_name}:")
            print(f"   Description: {policy_info.get('description', 'No description')}")
            
            config = policy_info.get('configuration', {})
            if config:
                print(f"   Configuration:")
                for key, value in config.items():
                    print(f"     {key}: {value}")
    
    async def _run_search(self, query: str):
        """Run a basic search query."""
        if not query:
            print("❌ Please provide a search query")
            return
        
        print(f"\n🔍 Searching for: '{query}'")
        start_time = time.time()
        
        try:
            result = await self.dispatcher.dispatch_query(
                query=query,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL,
                limit=10
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            if result.success:
                print(f"✅ Found {len(result.results)} results in {response_time:.1f}ms")
                print(f"🎯 Search mode: {result.search_mode_used}")
                print(f"🔧 Backends used: {', '.join(result.backends_used)}")
                
                # Show top results
                for i, context in enumerate(result.results[:5], 1):
                    print(f"\n{i}. [{context.type.value}] Score: {context.score:.2f}")
                    print(f"   {context.text[:100]}{'...' if len(context.text) > 100 else ''}")
                    print(f"   Tags: {', '.join(context.tags[:5])}")
                
                # Store for session tracking
                self.session_results.append({
                    'query': query,
                    'response_time_ms': response_time,
                    'result_count': len(result.results),
                    'search_mode_used': result.search_mode_used,
                    'backends_used': result.backends_used,
                    'timestamp': datetime.now().isoformat()
                })
                
            else:
                print(f"❌ Search failed in {response_time:.1f}ms")
                
        except Exception as e:
            print(f"❌ Search error: {e}")
    
    async def _run_advanced_search(self, query: str):
        """Run an advanced search with interactive parameter selection."""
        if not query:
            print("❌ Please provide a search query")
            return
        
        print(f"\n🔍 Advanced Search Setup for: '{query}'")
        print("-" * 50)
        
        # Search mode selection
        print("\n🎯 Select Search Mode:")
        search_modes = list(SearchMode)
        for i, mode in enumerate(search_modes, 1):
            print(f"  {i}. {mode.value}")
        
        try:
            mode_choice = input("Enter choice (1-5) or press Enter for default: ").strip()
            if mode_choice:
                search_mode = search_modes[int(mode_choice) - 1]
            else:
                search_mode = SearchMode.HYBRID
        except (ValueError, IndexError):
            search_mode = SearchMode.HYBRID
            print("Using default: HYBRID")
        
        # Dispatch policy selection
        print("\n🚀 Select Dispatch Policy:")
        dispatch_policies = list(DispatchPolicy)
        for i, policy in enumerate(dispatch_policies, 1):
            print(f"  {i}. {policy.value}")
        
        try:
            policy_choice = input("Enter choice (1-4) or press Enter for default: ").strip()
            if policy_choice:
                dispatch_policy = dispatch_policies[int(policy_choice) - 1]
            else:
                dispatch_policy = DispatchPolicy.PARALLEL
        except (ValueError, IndexError):
            dispatch_policy = DispatchPolicy.PARALLEL
            print("Using default: PARALLEL")
        
        # Ranking policy selection
        print("\n📋 Select Ranking Policy:")
        ranking_policies = self.dispatcher.get_available_ranking_policies()
        for i, policy in enumerate(ranking_policies, 1):
            print(f"  {i}. {policy}")
        
        try:
            ranking_choice = input("Enter choice or press Enter for default: ").strip()
            if ranking_choice:
                ranking_policy = ranking_policies[int(ranking_choice) - 1]
            else:
                ranking_policy = "default"
        except (ValueError, IndexError):
            ranking_policy = "default"
            print("Using default ranking policy")
        
        # Content type filter
        print("\n📄 Filter by Content Types (optional):")
        content_types = [ct.value for ct in ContentType]
        for i, ct in enumerate(content_types, 1):
            print(f"  {i}. {ct}")
        
        content_filter = input("Enter numbers (comma-separated) or press Enter to skip: ").strip()
        content_type_filter = None
        if content_filter:
            try:
                indices = [int(x.strip()) - 1 for x in content_filter.split(',')]
                content_type_filter = [content_types[i] for i in indices]
            except (ValueError, IndexError):
                print("Invalid content type selection, skipping filter")
        
        # Run the search
        print(f"\n🚀 Running advanced search...")
        start_time = time.time()
        
        try:
            result = await self.dispatcher.dispatch_query(
                query=query,
                search_mode=search_mode,
                dispatch_policy=dispatch_policy,
                ranking_policy=ranking_policy,
                limit=15,
                content_types=content_type_filter
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            if result.success:
                print(f"✅ Advanced search completed in {response_time:.1f}ms")
                print(f"📊 Configuration:")
                print(f"   Search Mode: {result.search_mode_used}")
                print(f"   Dispatch Policy: {dispatch_policy.value}")
                print(f"   Ranking Policy: {ranking_policy}")
                print(f"   Content Filter: {content_type_filter or 'None'}")
                print(f"   Backends Used: {', '.join(result.backends_used)}")
                
                print(f"\n📋 Results ({len(result.results)} found):")
                for i, context in enumerate(result.results[:8], 1):
                    print(f"\n{i}. [{context.type.value}] Score: {context.score:.3f} | Source: {context.source.value}")
                    print(f"   {context.text[:120]}{'...' if len(context.text) > 120 else ''}")
                    if context.tags:
                        print(f"   🏷️  {', '.join(context.tags[:6])}")
                
                # Store for session tracking
                self.session_results.append({
                    'query': query,
                    'search_mode': search_mode.value,
                    'dispatch_policy': dispatch_policy.value,
                    'ranking_policy': ranking_policy,
                    'response_time_ms': response_time,
                    'result_count': len(result.results),
                    'search_mode_used': result.search_mode_used,
                    'backends_used': result.backends_used,
                    'content_filter': content_type_filter,
                    'timestamp': datetime.now().isoformat()
                })
                
            else:
                print(f"❌ Advanced search failed in {response_time:.1f}ms")
                
        except Exception as e:
            print(f"❌ Advanced search error: {e}")
    
    async def _run_benchmark(self):
        """Run performance benchmark tests."""
        print("\n🏃 Running Performance Benchmark...")
        print("-" * 40)
        
        benchmark_queries = [
            "python function authentication",
            "javascript async fetch",
            "database configuration",
            "system architecture design",
            "api documentation guide"
        ]
        
        results = []
        
        for i, query in enumerate(benchmark_queries, 1):
            print(f"📊 Benchmark {i}/5: '{query}'")
            
            start_time = time.time()
            try:
                result = await self.dispatcher.dispatch_query(
                    query=query,
                    search_mode=SearchMode.HYBRID,
                    dispatch_policy=DispatchPolicy.PARALLEL,
                    limit=10
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append({
                    'query': query,
                    'response_time_ms': response_time,
                    'result_count': len(result.results) if result.success else 0,
                    'success': result.success
                })
                
                status_emoji = "✅" if result.success else "❌"
                print(f"  {status_emoji} {response_time:.1f}ms ({len(result.results) if result.success else 0} results)")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results.append({
                    'query': query,
                    'response_time_ms': 0,
                    'result_count': 0,
                    'success': False,
                    'error': str(e)
                })
        
        # Benchmark summary
        successful_results = [r for r in results if r['success']]
        if successful_results:
            avg_time = sum(r['response_time_ms'] for r in successful_results) / len(successful_results)
            min_time = min(r['response_time_ms'] for r in successful_results)
            max_time = max(r['response_time_ms'] for r in successful_results)
            
            print(f"\n🏆 Benchmark Summary:")
            print(f"   Successful queries: {len(successful_results)}/{len(benchmark_queries)}")
            print(f"   Average response time: {avg_time:.1f}ms")
            print(f"   Fastest query: {min_time:.1f}ms")
            print(f"   Slowest query: {max_time:.1f}ms")
        else:
            print("\n❌ All benchmark queries failed")
    
    def _show_session_results(self):
        """Show results from current session."""
        if not self.session_results:
            print("📊 No queries executed in this session yet.")
            return
        
        print(f"\n📊 Session Results ({len(self.session_results)} queries):")
        print("-" * 50)
        
        for i, result in enumerate(self.session_results, 1):
            print(f"\n{i}. Query: '{result['query']}'")
            print(f"   Time: {result['response_time_ms']:.1f}ms")
            print(f"   Results: {result['result_count']}")
            if 'search_mode_used' in result:
                print(f"   Mode: {result['search_mode_used']}")
            if 'backends_used' in result:
                print(f"   Backends: {', '.join(result['backends_used'])}")
    
    def _export_session_results(self):
        """Export session results to JSON file."""
        if not self.session_results:
            print("📊 No session data to export.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"veris_query_session_{timestamp}.json"
        
        export_data = {
            'session_info': {
                'timestamp': datetime.now().isoformat(),
                'query_count': len(self.session_results),
                'use_mock_backends': self.use_mock_backends
            },
            'queries': self.session_results,
            'performance_summary': {
                'avg_response_time_ms': sum(r['response_time_ms'] for r in self.session_results) / len(self.session_results),
                'total_results': sum(r['result_count'] for r in self.session_results)
            }
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"✅ Session data exported to: {filename}")
        except Exception as e:
            print(f"❌ Export failed: {e}")


async def main():
    """Main entry point for the CLI query simulator."""
    parser = argparse.ArgumentParser(description="Veris Memory CLI Query Simulator")
    parser.add_argument(
        "--real-backends", 
        action="store_true",
        help="Use real backends instead of mock backends"
    )
    parser.add_argument(
        "--query",
        help="Run a single query and exit"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true", 
        help="Run benchmark tests and exit"
    )
    
    args = parser.parse_args()
    
    # Initialize simulator
    simulator = QuerySimulator(use_mock_backends=not args.real_backends)
    await simulator.initialize()
    
    if args.query:
        # Single query mode
        await simulator._run_search(args.query)
    elif args.benchmark:
        # Benchmark mode
        await simulator._run_benchmark()
    else:
        # Interactive mode
        await simulator.run_interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())