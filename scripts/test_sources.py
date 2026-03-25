#!/usr/bin/env python3
"""Test connectivity to all data sources with detailed debugging."""

from __future__ import annotations

import sys
import traceback

from core.config import load_config
from core.query_builder import build_source_query
from core.tools.sources.registry import SourceRegistry


def test_source(source_name: str, connector, user) -> dict:
    """Test a single source connectivity with detailed error info."""
    try:
        results = connector.fetch_candidates(user=user, limit=3)
        return {
            "source": source_name,
            "status": "ok",
            "candidates_found": len(results),
            "results": results,
            "error": None,
            "traceback": None,
        }
    except Exception as e:
        return {
            "source": source_name,
            "status": "error",
            "candidates_found": 0,
            "results": [],
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def main():
    print("=" * 70)
    print("Testing Data Source Connectivity (Detailed)")
    print("=" * 70)

    app_config = load_config()
    registry = SourceRegistry()

    # Use first user for testing
    if not app_config.users:
        print("No users configured!")
        sys.exit(1)

    test_user = app_config.users[0]

    # Determine query mode from config
    query_mode = "interests" if app_config.global_config.auto_query_from_interests else "manual"
    if app_config.global_config.auto_query_mode in ("manual", "interests", "merge"):
        query_mode = app_config.global_config.auto_query_mode

    # Build base query for display
    base_query = build_source_query(
        user=test_user,
        source_name="arxiv",
        mode=query_mode,
        source_query_templates=getattr(app_config.global_config, 'source_query_templates', None),
    )

    print(f"\nTest user: {test_user.user_id}")
    print(f"Interests: {test_user.interests}")
    print(f"Base query: '{base_query}'")
    print(f"Query mode: {query_mode}")
    print(f"Enabled sources: {test_user.enabled_sources}")
    print("-" * 70)

    # Build connectors for all configured sources
    connectors = registry.build_for_user(app_config=app_config, user=test_user)

    if not connectors:
        print("No connectors available. Check config.yaml sources configuration.")
        print(f"Available sources in config: {list(app_config.sources.keys())}")
        sys.exit(1)

    print(f"\nFound {len(connectors)} connectors: {[c.source_name for c in connectors]}")
    print("-" * 70)

    results = []
    for connector in connectors:
        source_name = connector.source_name
        print(f"\n>>> Testing {source_name}...")

        # Build source-specific query
        source_query = build_source_query(
            user=test_user,
            source_name=source_name,
            mode=query_mode,
            source_query_templates=getattr(app_config.global_config, 'source_query_templates', None),
        )
        print(f"    Query: '{source_query}'")

        # Create a test user with the source-specific query
        source_user = test_user.model_copy(update={"search_query": source_query})

        result = test_source(source_name, connector, source_user)
        results.append(result)

        if result["status"] == "ok":
            print(f"    [OK] {result['candidates_found']} candidates found")
            if result["candidates_found"] > 0:
                print(f"    Sample titles:")
                for i, paper in enumerate(result["results"][:3], 1):
                    title = getattr(paper, 'title', None) or paper.get('title', 'N/A')
                    print(f"      {i}. {title}")
        else:
            print(f"    [FAILED]")
            print(f"    Error: {result['error']}")
            if result["traceback"]:
                print(f"    Traceback:")
                for line in result["traceback"].split('\n')[:10]:
                    print(f"      {line}")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    error_count = len(results) - ok_count

    print(f"Total sources: {len(results)}")
    print(f"OK: {ok_count}")
    print(f"Failed: {error_count}")

    if error_count > 0:
        print("\nFailed sources:")
        for r in results:
            if r["status"] == "error":
                print(f"  - {r['source']}: {r['error']}")

    # Check for sources in config but not built
    configured_sources = set(app_config.sources.keys())
    enabled_sources = set(test_user.enabled_sources)
    built_sources = set(c.source_name for c in connectors)

    print(f"\nSources in config: {configured_sources}")
    print(f"Sources enabled for user: {enabled_sources}")
    print(f"Sources actually built: {built_sources}")

    missing = enabled_sources - built_sources
    if missing:
        print(f"\nWARNING: Enabled but not built: {missing}")
        for name in missing:
            cfg = app_config.sources.get(name)
            if cfg:
                print(f"  - {name}: enabled={cfg.enabled}, priority={cfg.priority}")

    return error_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
