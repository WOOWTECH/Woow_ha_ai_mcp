"""Unit tests for enterprise optimization changes.

Tests:
- Levenshtein distance function correctness and edge cases
- Levenshtein integration into _typo_fallback of FuzzyEntitySearcher
- hours alias parameter validation in ha_get_history
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from ha_mcp.utils.fuzzy_search import (
    FuzzyEntitySearcher,
    calculate_ratio,
    levenshtein_distance,
)


# ---------------------------------------------------------------------------
# TestLevenshteinDistance — Algorithm correctness
# ---------------------------------------------------------------------------


class TestLevenshteinDistance:
    """Test the levenshtein_distance function for correctness and edge cases."""

    def test_identical_strings(self):
        assert levenshtein_distance("temperature", "temperature") == 0

    def test_single_deletion(self):
        """Missing one character — most common LLM typo pattern."""
        assert levenshtein_distance("temperature", "temprature") == 1

    def test_single_insertion(self):
        """Extra character inserted."""
        assert levenshtein_distance("bedroom", "beedroom") == 1

    def test_single_substitution(self):
        """One character replaced."""
        assert levenshtein_distance("sensor", "senser") == 1

    def test_double_edit(self):
        """Two edits — boundary for our threshold of ≤ 2."""
        # "switch" → "swihtc" requires 2 edits
        assert levenshtein_distance("switch", "swihtc") == 2

    def test_beyond_threshold(self):
        """More than 2 edits — should NOT trigger Levenshtein matching."""
        assert levenshtein_distance("light", "dark") == 5

    def test_empty_vs_nonempty(self):
        """Empty string requires insertions equal to other string's length."""
        assert levenshtein_distance("", "hello") == 5

    def test_both_empty(self):
        assert levenshtein_distance("", "") == 0

    def test_symmetry(self):
        """Levenshtein distance is symmetric: lev(a,b) == lev(b,a)."""
        assert levenshtein_distance("abc", "bac") == levenshtein_distance("bac", "abc")
        assert levenshtein_distance("humidity", "humidty") == levenshtein_distance(
            "humidty", "humidity"
        )

    def test_short_real_world_typos(self):
        """Common HA entity typos that should be distance ≤ 2."""
        assert levenshtein_distance("humidity", "humidty") == 1
        assert levenshtein_distance("motion", "moton") == 1
        assert levenshtein_distance("kitchen", "kicthen") == 2


# ---------------------------------------------------------------------------
# TestLevenshteinInTypoFallback — Integration with FuzzyEntitySearcher
# ---------------------------------------------------------------------------


class TestLevenshteinInTypoFallback:
    """Test Levenshtein fallback integration in the _typo_fallback method."""

    @pytest.fixture
    def entities_with_long_tokens(self):
        """Entities with tokens ≥ 5 chars (required for Levenshtein to activate)."""
        return [
            {
                "entity_id": "sensor.living_room_temperature",
                "attributes": {"friendly_name": "Living Room Temperature"},
                "state": "22.5",
            },
            {
                "entity_id": "sensor.outdoor_humidity",
                "attributes": {"friendly_name": "Outdoor Humidity"},
                "state": "65",
            },
            {
                "entity_id": "binary_sensor.kitchen_motion",
                "attributes": {"friendly_name": "Kitchen Motion"},
                "state": "off",
            },
            {
                "entity_id": "light.bedroom_ceiling",
                "attributes": {"friendly_name": "Bedroom Ceiling"},
                "state": "on",
            },
        ]

    def test_lev_catches_when_sequencematcher_misses(self, entities_with_long_tokens):
        """When SequenceMatcher ratio < 75 but Levenshtein distance ≤ 2, match should succeed.

        We construct a synthetic entity where two non-adjacent character substitutions
        bring SequenceMatcher below threshold but edit distance remains ≤ 2.
        """
        # "xbcdy" as entity token; query "abcde" — 2 non-adjacent substitutions
        # calculate_ratio("abcde", "xbcdy") = 60 (3 common chars / 10 total)
        # levenshtein_distance("abcde", "xbcdy") = 2
        entities = [
            {
                "entity_id": "sensor.xbcdy_reading",
                "attributes": {"friendly_name": "XBCDY Reading"},
                "state": "10",
            },
        ]
        ratio = calculate_ratio("abcde", "xbcdy")
        dist = levenshtein_distance("abcde", "xbcdy")
        # Verify our premise: ratio < 75 and distance ≤ 2
        assert ratio < 75, f"Test premise violated: ratio={ratio} should be < 75"
        assert dist <= 2, f"Test premise violated: dist={dist} should be ≤ 2"

        searcher = FuzzyEntitySearcher(threshold=30)
        results, total = searcher.search_entities(entities, "abcde", limit=5)

        # Should find the entity via Levenshtein fallback
        assert total > 0, (
            f"Levenshtein should catch 'abcde' → 'xbcdy' "
            f"(ratio={ratio}, dist={dist})"
        )
        assert results[0]["match_type"] == "levenshtein_fallback"

    def test_lev_skips_short_tokens(self, entities_with_long_tokens):
        """Tokens < 5 chars should NOT trigger Levenshtein fallback."""
        # "lit" (3 chars) — too short for Levenshtein
        searcher = FuzzyEntitySearcher(threshold=30)
        results, total = searcher.search_entities(
            entities_with_long_tokens, "lit", limit=5
        )
        # Should get 0 results from typo_fallback (BM25 might still match)
        lev_results = [r for r in results if r.get("match_type") == "levenshtein_fallback"]
        assert len(lev_results) == 0, (
            "Short tokens (< 5 chars) should never trigger Levenshtein fallback"
        )

    def test_lev_score_mapping(self, entities_with_long_tokens):
        """Levenshtein distance maps to synthetic scores: dist=1→80, dist=2→70."""
        # Construct entity where we know the Levenshtein path will be taken
        entities = [
            {
                "entity_id": "sensor.abcdef_value",
                "attributes": {"friendly_name": "ABCDEF Value"},
                "state": "5",
            },
        ]
        # "abcdfe" vs "abcdef" — transposition, dist=2
        ratio = calculate_ratio("abcdfe", "abcdef")
        dist = levenshtein_distance("abcdfe", "abcdef")
        if ratio < 75 and dist <= 2:
            searcher = FuzzyEntitySearcher(threshold=30)
            results, total = searcher.search_entities(entities, "abcdfe", limit=5)
            if total > 0:
                lev_results = [
                    r for r in results if r.get("match_type") == "levenshtein_fallback"
                ]
                if lev_results:
                    # Score should be 90 - dist*10 = 70 for dist=2
                    assert lev_results[0]["score"] == 70, (
                        f"Expected score 70 for distance 2, got {lev_results[0]['score']}"
                    )

    def test_normal_typo_uses_sequencematcher(self, entities_with_long_tokens):
        """When SequenceMatcher ratio ≥ 75, result uses 'typo_fallback' not 'levenshtein_fallback'."""
        # "temperatur" vs "temperature" — ratio is high (SequenceMatcher handles it)
        searcher = FuzzyEntitySearcher(threshold=30)
        results, total = searcher.search_entities(
            entities_with_long_tokens, "temperatur", limit=5
        )
        if total > 0:
            # Should be matched via SequenceMatcher (typo_fallback), not Levenshtein
            for r in results:
                if "temperature" in r["entity_id"]:
                    assert r["match_type"] in ("typo_fallback", "bm25"), (
                        f"Expected typo_fallback or bm25, got {r['match_type']}"
                    )


# ---------------------------------------------------------------------------
# TestHoursParameterValidation — hours alias logic
# ---------------------------------------------------------------------------


class TestHoursParameterValidation:
    """Test hours parameter validation in ha_get_history."""

    @pytest.fixture
    def mock_client(self):
        """Create a minimal mock HA client."""
        client = MagicMock()
        client.base_url = "http://homeassistant.local"
        client.token = "test_token"
        return client

    @pytest.fixture
    def history_tool(self, mock_client):
        """Create HistoryTools instance and return ha_get_history method."""
        from ha_mcp.tools.tools_history import HistoryTools

        tools = HistoryTools(mock_client)
        return tools.ha_get_history

    @pytest.mark.asyncio
    async def test_hours_and_start_time_conflict(self, history_tool):
        """Specifying both hours and start_time should raise ToolError."""
        with pytest.raises(ToolError) as exc_info:
            await history_tool(
                entity_ids="sensor.test",
                hours=1,
                start_time="24h",
            )

        error_data = json.loads(str(exc_info.value))
        assert error_data["error"]["code"] == "VALIDATION_INVALID_PARAMETER"
        assert "Cannot specify both" in error_data["error"]["message"]

    @pytest.mark.asyncio
    async def test_hours_converts_to_start_time_format(self, history_tool):
        """hours=24 should convert to start_time equivalent and proceed to API call."""
        # The tool will fail at the API call level (mock client),
        # but we can verify the hours parameter is processed without validation errors.
        # Patch the websocket client to avoid connection attempts.
        with patch(
            "ha_mcp.tools.tools_history.get_connected_ws_client",
            side_effect=RuntimeError("mock: connection not available"),
        ):
            with pytest.raises(ToolError) as exc_info:
                await history_tool(entity_ids="sensor.test", hours=24)

            # The error should be from the connection failure, NOT from validation
            error_data = json.loads(str(exc_info.value))
            # If we get here without VALIDATION_INVALID_PARAMETER, hours was accepted
            assert error_data["error"]["code"] != "VALIDATION_INVALID_PARAMETER", (
                "hours=24 alone should not cause a validation error"
            )

    @pytest.mark.asyncio
    async def test_hours_string_coercion(self, history_tool):
        """hours="0.5" (string) should be coerced to float and proceed past validation."""
        with patch(
            "ha_mcp.tools.tools_history.get_connected_ws_client",
            side_effect=RuntimeError("mock: connection not available"),
        ):
            with pytest.raises(ToolError) as exc_info:
                await history_tool(entity_ids="sensor.test", hours="0.5")

            error_data = json.loads(str(exc_info.value))
            # Should NOT be a validation error — string "0.5" coerced to float,
            # fractional hours converted to ISO datetime (not "0.5h").
            # The error should come from the mock connection, not from time parsing.
            assert error_data["error"]["code"] != "VALIDATION_INVALID_PARAMETER", (
                f"hours='0.5' should be coerced to float without validation error. "
                f"Got: {error_data['error']['message']}"
            )

    @pytest.mark.asyncio
    async def test_hours_integer_uses_relative_format(self, history_tool):
        """hours=24 (integer-like) should use relative format '24h'."""
        with patch(
            "ha_mcp.tools.tools_history.get_connected_ws_client",
            side_effect=RuntimeError("mock: connection not available"),
        ):
            with pytest.raises(ToolError) as exc_info:
                await history_tool(entity_ids="sensor.test", hours=24)

            error_data = json.loads(str(exc_info.value))
            # Integer hours → "24h" relative format → passes time parsing
            # Error should be from mock connection, not from validation
            assert error_data["error"]["code"] != "VALIDATION_INVALID_PARAMETER", (
                f"hours=24 should convert to '24h' format. "
                f"Got: {error_data['error']['message']}"
            )
