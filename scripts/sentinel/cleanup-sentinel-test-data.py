#!/usr/bin/env python3
"""
Cleanup script for Sentinel test data in Veris Memory.

PR #399: Sentinel S2 Golden Fact Recall was storing test facts without cleanup,
causing database bloat. This script removes existing sentinel test data.

Usage:
    python scripts/sentinel/cleanup-sentinel-test-data.py [--dry-run] [--batch-size N]

Options:
    --dry-run       Show what would be deleted without actually deleting
    --batch-size N  Delete in batches of N (default: 1000)
    --url URL       Veris Memory URL (default: http://localhost:8000)
"""

import argparse
import json
import sys
import time
from typing import Dict, Any
import urllib.request
import urllib.error


def query_graph(base_url: str, cypher_query: str) -> Dict[str, Any]:
    """Execute a Cypher query via the query_graph API."""
    url = f"{base_url}/tools/query_graph"
    payload = json.dumps({"query": cypher_query}).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else "No error body"
        return {"error": f"HTTP {e.code}: {error_body}"}
    except urllib.error.URLError as e:
        return {"error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def count_sentinel_data(base_url: str) -> Dict[str, int]:
    """Count sentinel test data by category."""
    counts = {}

    # Count all contexts
    result = query_graph(base_url, "MATCH (n:Context) RETURN count(n) as total")
    if "error" not in result:
        results = result.get("results", [])
        counts["total_contexts"] = results[0].get("total", 0) if results else 0

    # Count sentinel test data (metadata contains sentinel marker)
    # S2 uses: type=log, metadata contains sentinel=True and test_type=golden_recall
    result = query_graph(base_url, """
        MATCH (n:Context)
        WHERE n.type = 'log'
          AND n.metadata CONTAINS 'sentinel'
          AND n.metadata CONTAINS 'golden_recall'
        RETURN count(n) as sentinel_count
    """)
    if "error" not in result:
        results = result.get("results", [])
        counts["sentinel_test_data"] = results[0].get("sentinel_count", 0) if results else 0

    # Count by author prefix (sentinel uses sentinel_test_ prefix)
    result = query_graph(base_url, """
        MATCH (n:Context)
        WHERE n.metadata CONTAINS 'sentinel_test_'
        RETURN count(n) as by_author
    """)
    if "error" not in result:
        results = result.get("results", [])
        counts["sentinel_by_author"] = results[0].get("by_author", 0) if results else 0

    return counts


def delete_sentinel_data_batch(base_url: str, batch_size: int) -> Dict[str, Any]:
    """Delete a batch of sentinel test data."""
    # Delete contexts that match sentinel test pattern
    query = f"""
        MATCH (n:Context)
        WHERE n.type = 'log'
          AND n.metadata CONTAINS 'sentinel'
          AND n.metadata CONTAINS 'golden_recall'
        WITH n LIMIT {batch_size}
        DETACH DELETE n
        RETURN count(n) as deleted
    """

    result = query_graph(base_url, query)
    if "error" in result:
        return {"success": False, "error": result["error"]}

    results = result.get("results", [])
    deleted = results[0].get("deleted", 0) if results else 0
    return {"success": True, "deleted": deleted}


def delete_sentinel_data_by_author(base_url: str, batch_size: int) -> Dict[str, Any]:
    """Delete sentinel test data by author pattern."""
    query = f"""
        MATCH (n:Context)
        WHERE n.metadata CONTAINS 'sentinel_test_'
        WITH n LIMIT {batch_size}
        DETACH DELETE n
        RETURN count(n) as deleted
    """

    result = query_graph(base_url, query)
    if "error" in result:
        return {"success": False, "error": result["error"]}

    results = result.get("results", [])
    deleted = results[0].get("deleted", 0) if results else 0
    return {"success": True, "deleted": deleted}


def main():
    parser = argparse.ArgumentParser(
        description="Clean up Sentinel test data from Veris Memory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Delete in batches of N (default: 1000)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Veris Memory URL (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    # Security: Validate batch_size bounds to prevent injection/DoS
    if not 1 <= args.batch_size <= 10000:
        print(f"ERROR: batch_size must be between 1 and 10000, got {args.batch_size}")
        sys.exit(1)

    print("=" * 60)
    print("Veris Memory Sentinel Test Data Cleanup")
    print("=" * 60)
    print(f"Target URL: {args.url}")
    print(f"Batch size: {args.batch_size}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Count existing data
    print("Counting sentinel test data...")
    counts = count_sentinel_data(args.url)

    if not counts:
        print("ERROR: Could not connect to Veris Memory")
        sys.exit(1)

    print(f"  Total contexts in database: {counts.get('total_contexts', 'unknown')}")
    print(f"  Sentinel test data (by metadata): {counts.get('sentinel_test_data', 'unknown')}")
    print(f"  Sentinel test data (by author): {counts.get('sentinel_by_author', 'unknown')}")
    print()

    sentinel_count = max(
        counts.get('sentinel_test_data', 0),
        counts.get('sentinel_by_author', 0)
    )

    if sentinel_count == 0:
        print("No sentinel test data found. Nothing to clean up.")
        sys.exit(0)

    if args.dry_run:
        print(f"DRY RUN: Would delete approximately {sentinel_count} sentinel test entries")
        print("Run without --dry-run to actually delete the data")
        sys.exit(0)

    # Confirm deletion
    print(f"About to delete approximately {sentinel_count} sentinel test entries.")
    response = input("Continue? [y/N]: ")
    if response.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    # Delete in batches
    total_deleted = 0
    batch_num = 0

    print()
    print("Deleting sentinel test data...")

    while True:
        batch_num += 1

        # Try metadata-based deletion first
        result = delete_sentinel_data_batch(args.url, args.batch_size)

        if not result["success"]:
            # Fall back to author-based deletion
            result = delete_sentinel_data_by_author(args.url, args.batch_size)

        if not result["success"]:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
            break

        deleted = result["deleted"]
        if deleted == 0:
            break

        total_deleted += deleted
        print(f"  Batch {batch_num}: Deleted {deleted} entries (total: {total_deleted})")

        # Small delay to avoid overwhelming the database
        time.sleep(0.5)

    print()
    print("=" * 60)
    print(f"Cleanup complete. Total deleted: {total_deleted}")
    print("=" * 60)

    # Verify final counts
    print()
    print("Verifying cleanup...")
    final_counts = count_sentinel_data(args.url)
    print(f"  Total contexts remaining: {final_counts.get('total_contexts', 'unknown')}")
    print(f"  Sentinel test data remaining: {final_counts.get('sentinel_test_data', 'unknown')}")


if __name__ == "__main__":
    main()
