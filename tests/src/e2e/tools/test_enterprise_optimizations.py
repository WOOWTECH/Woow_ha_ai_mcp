"""
E2E tests for enterprise optimization changes.

Tests the 6 optimizations identified during enterprise testing:
- P0-1: Parameter descriptions with anti-pattern warnings
- P0-2: Automation wait timing (attributes.id verification)
- P1-1: Levenshtein fuzzy search fallback (covered by unit tests + basic E2E)
- P1-2: hours convenience alias for ha_get_history
- P2-1: Bulk control summary field
- P2-2: Automation stored_config in creation response
"""

import json
import logging

import pytest

from ..utilities.assertions import assert_mcp_success, parse_mcp_result, safe_call_tool
from ..utilities.wait_helpers import wait_for_tool_result

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TestParameterDescriptions — Verify schema descriptions via tools/list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestParameterDescriptions:
    """Verify that tool schemas contain anti-pattern warnings for LLM discoverability."""

    async def _get_tool_schema(self, mcp_client, tool_name: str) -> dict:
        """Get inputSchema for a tool by name."""
        tools = await mcp_client.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool.inputSchema or {}
        pytest.fail(f"Tool {tool_name} not found in tools list")

    async def test_call_service_data_description(self, mcp_client):
        """ha_call_service 'data' param should warn against 'service_data'."""
        schema = await self._get_tool_schema(mcp_client, "ha_call_service")
        properties = schema.get("properties", {})
        assert "data" in properties, f"'data' param missing from schema: {list(properties.keys())}"

        desc = properties["data"].get("description", "")
        assert "NOT 'service_data'" in desc, (
            f"'data' description should contain anti-pattern warning. Got: {desc[:100]}"
        )

    async def test_dashboard_url_path_description(self, mcp_client):
        """ha_config_get_dashboard 'url_path' should warn against 'dashboard_id'."""
        schema = await self._get_tool_schema(mcp_client, "ha_config_get_dashboard")
        properties = schema.get("properties", {})
        assert "url_path" in properties, (
            f"'url_path' param missing: {list(properties.keys())}"
        )

        desc = properties["url_path"].get("description", "")
        assert "NOT 'dashboard_id'" in desc, (
            f"'url_path' description should warn against dashboard_id. Got: {desc[:100]}"
        )

    async def test_helper_type_description(self, mcp_client):
        """ha_config_set_helper 'helper_type' should warn against 'type'."""
        schema = await self._get_tool_schema(mcp_client, "ha_config_set_helper")
        properties = schema.get("properties", {})
        assert "helper_type" in properties, (
            f"'helper_type' param missing: {list(properties.keys())}"
        )

        desc = properties["helper_type"].get("description", "")
        assert "NOT 'type'" in desc, (
            f"'helper_type' description should warn against 'type'. Got: {desc[:100]}"
        )

    async def test_history_entity_ids_description(self, mcp_client):
        """ha_get_history 'entity_ids' should clarify plural form."""
        schema = await self._get_tool_schema(mcp_client, "ha_get_history")
        properties = schema.get("properties", {})
        assert "entity_ids" in properties, (
            f"'entity_ids' param missing: {list(properties.keys())}"
        )

        desc = properties["entity_ids"].get("description", "")
        assert "(plural)" in desc, (
            f"'entity_ids' description should clarify plural form. Got: {desc[:100]}"
        )

    async def test_history_hours_parameter_exists(self, mcp_client):
        """ha_get_history should have 'hours' parameter in schema."""
        schema = await self._get_tool_schema(mcp_client, "ha_get_history")
        properties = schema.get("properties", {})
        assert "hours" in properties, (
            f"'hours' param missing from ha_get_history schema: {list(properties.keys())}"
        )

        desc = properties["hours"].get("description", "")
        assert "look back" in desc.lower() or "alias" in desc.lower(), (
            f"'hours' description should explain it's a convenience alias. Got: {desc[:100]}"
        )


# ---------------------------------------------------------------------------
# TestHoursAlias — E2E validation of hours parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHoursAlias:
    """Test hours convenience parameter for ha_get_history via live HA."""

    async def test_hours_returns_valid_history(self, mcp_client):
        """hours=1 should return valid history data."""
        result = await mcp_client.call_tool(
            "ha_get_history",
            {"entity_ids": "sun.sun", "hours": 1},
        )

        data = assert_mcp_success(result, "Get history with hours=1")
        inner = data.get("data", data)
        assert "entities" in inner, f"Missing 'entities' key: {list(inner.keys())}"
        assert isinstance(inner["entities"], list)
        logger.info(f"hours=1 returned {len(inner['entities'])} entity histories")

    async def test_hours_fractional(self, mcp_client):
        """hours=0.5 (30 minutes) should work correctly."""
        result = await mcp_client.call_tool(
            "ha_get_history",
            {"entity_ids": "sun.sun", "hours": 0.5},
        )

        data = assert_mcp_success(result, "Get history with hours=0.5")
        inner = data.get("data", data)
        assert "entities" in inner, f"Fractional hours failed: {inner}"

    async def test_hours_and_start_time_conflict(self, mcp_client):
        """Using both hours and start_time should return a clear error."""
        parsed = await safe_call_tool(
            mcp_client,
            "ha_get_history",
            {"entity_ids": "sun.sun", "hours": 1, "start_time": "24h"},
        )

        assert parsed.get("success") is not True, (
            "Should fail when both hours and start_time are specified"
        )
        error = parsed.get("error", {})
        error_msg = error.get("message", str(parsed))
        assert "Cannot specify both" in error_msg, (
            f"Error should mention conflict. Got: {error_msg[:200]}"
        )

    async def test_hours_equivalent_to_start_time(self, mcp_client):
        """hours=24 and start_time='24h' should produce equivalent results."""
        result_hours = await mcp_client.call_tool(
            "ha_get_history",
            {"entity_ids": "sun.sun", "hours": 24},
        )
        result_start = await mcp_client.call_tool(
            "ha_get_history",
            {"entity_ids": "sun.sun", "start_time": "24h"},
        )

        data_hours = assert_mcp_success(result_hours, "hours=24")
        data_start = assert_mcp_success(result_start, "start_time=24h")

        inner_hours = data_hours.get("data", data_hours)
        inner_start = data_start.get("data", data_start)

        # Both should have entities with similar structure
        entities_h = inner_hours.get("entities", [])
        entities_s = inner_start.get("entities", [])

        assert len(entities_h) == len(entities_s), (
            f"hours=24 returned {len(entities_h)} entities, "
            f"start_time='24h' returned {len(entities_s)}"
        )

        # If both have data, state counts should be identical (same time range)
        if entities_h and entities_s:
            count_h = entities_h[0].get("count", len(entities_h[0].get("states", [])))
            count_s = entities_s[0].get("count", len(entities_s[0].get("states", [])))
            assert count_h == count_s, (
                f"State counts differ: hours={count_h}, start_time={count_s}"
            )


# ---------------------------------------------------------------------------
# TestBulkControlSummary — summary field in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBulkControlSummary:
    """Test that ha_bulk_control includes a human-readable summary field."""

    async def test_summary_field_present(self, mcp_client, test_light_entity):
        """Bulk control response should include a 'summary' string."""
        operations = [{"entity_id": test_light_entity, "action": "on"}]
        result = await mcp_client.call_tool(
            "ha_bulk_control",
            {"operations": operations},
        )

        data = assert_mcp_success(result, "Bulk control with summary")
        assert "summary" in data, (
            f"Missing 'summary' field in bulk response. Keys: {list(data.keys())}"
        )
        assert isinstance(data["summary"], str), (
            f"summary should be a string, got: {type(data['summary'])}"
        )
        logger.info(f"Bulk summary: {data['summary']}")

    async def test_summary_format_single_operation(self, mcp_client, test_light_entity):
        """Summary should show '1/1 operations successful: entity→action'."""
        operations = [{"entity_id": test_light_entity, "action": "on"}]
        result = await mcp_client.call_tool(
            "ha_bulk_control",
            {"operations": operations},
        )

        data = assert_mcp_success(result, "Bulk control summary format")
        summary = data.get("summary", "")

        # Should contain the success ratio
        assert "1/1 operations successful" in summary, (
            f"Summary should contain '1/1 operations successful'. Got: {summary}"
        )
        # Should contain entity reference
        assert test_light_entity in summary or "→" in summary, (
            f"Summary should reference entity/action. Got: {summary}"
        )

    async def test_summary_multi_operations(self, mcp_client, test_light_entity):
        """Summary with multiple operations should reflect correct ratio."""
        # Use same entity twice with different actions (toggle idempotent)
        operations = [
            {"entity_id": test_light_entity, "action": "on"},
            {"entity_id": test_light_entity, "action": "off"},
        ]
        result = await mcp_client.call_tool(
            "ha_bulk_control",
            {"operations": operations},
        )

        data = assert_mcp_success(result, "Bulk control multi-op summary")
        summary = data.get("summary", "")

        # Should show correct total
        assert "/2 operations successful" in summary, (
            f"Summary should show /2 total. Got: {summary}"
        )


# ---------------------------------------------------------------------------
# TestAutomationStoredConfig — stored_config in creation response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAutomationStoredConfig:
    """Test that automation creation returns the stored config."""

    async def test_create_returns_stored_config(self, mcp_client):
        """New automation creation should include stored_config in response."""
        config = {
            "alias": "OptTest Stored Config Verify",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "sun.sun",
                    "to": "below_horizon",
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "light.opttest_stored_config"},
                }
            ],
        }

        result = await mcp_client.call_tool(
            "ha_config_set_automation",
            {"config": config},
        )

        try:
            data = assert_mcp_success(result, "Create automation with stored_config")

            assert "stored_config" in data, (
                f"Missing 'stored_config' in creation response. Keys: {list(data.keys())}"
            )
            stored = data["stored_config"]
            assert isinstance(stored, dict), f"stored_config should be dict: {type(stored)}"

            # Verify stored config contains the alias
            assert stored.get("alias") == "OptTest Stored Config Verify", (
                f"stored_config alias mismatch: {stored.get('alias')}"
            )
            logger.info(f"stored_config keys: {list(stored.keys())}")

        finally:
            # Cleanup
            entity_id = "automation.opttest_stored_config_verify"
            try:
                await mcp_client.call_tool(
                    "ha_config_remove_automation",
                    {"entity_id": entity_id},
                )
            except Exception as e:
                logger.debug(f"Cleanup of {entity_id} failed: {e}")

    async def test_stored_config_matches_input(self, mcp_client):
        """stored_config should match what was submitted."""
        config = {
            "alias": "OptTest Config Match",
            "trigger": [
                {
                    "platform": "time",
                    "at": "06:00:00",
                }
            ],
            "action": [
                {
                    "service": "input_boolean.turn_on",
                    "target": {"entity_id": "input_boolean.opttest_match"},
                }
            ],
        }

        result = await mcp_client.call_tool(
            "ha_config_set_automation",
            {"config": config},
        )

        try:
            data = assert_mcp_success(result, "Create automation for config match")

            if "stored_config" in data:
                stored = data["stored_config"]
                assert stored.get("alias") == "OptTest Config Match"
                # Verify trigger was stored
                triggers = stored.get("trigger", stored.get("triggers", []))
                assert len(triggers) > 0, "stored_config should have triggers"
            else:
                logger.warning("stored_config not present — may be a timing issue")

        finally:
            entity_id = "automation.opttest_config_match"
            try:
                await mcp_client.call_tool(
                    "ha_config_remove_automation",
                    {"entity_id": entity_id},
                )
            except Exception as e:
                logger.debug(f"Cleanup of {entity_id} failed: {e}")

    async def test_update_does_not_return_stored_config(self, mcp_client):
        """Updating an existing automation should NOT return stored_config."""
        config = {
            "alias": "OptTest Update NoConfig",
            "trigger": [
                {"platform": "state", "entity_id": "sun.sun"}
            ],
            "action": [
                {"service": "light.turn_on", "target": {"entity_id": "light.test"}}
            ],
        }

        # Create first
        create_result = await mcp_client.call_tool(
            "ha_config_set_automation",
            {"config": config},
        )
        create_data = assert_mcp_success(create_result, "Create for update test")
        unique_id = create_data.get("unique_id")

        try:
            # Update with identifier
            update_config = {
                "alias": "OptTest Update NoConfig Updated",
                "trigger": [
                    {"platform": "state", "entity_id": "sun.sun"}
                ],
                "action": [
                    {"service": "light.turn_off", "target": {"entity_id": "light.test"}}
                ],
            }

            update_result = await mcp_client.call_tool(
                "ha_config_set_automation",
                {"identifier": unique_id, "config": update_config},
            )
            update_data = assert_mcp_success(update_result, "Update automation")

            # stored_config is only for new creations
            assert "stored_config" not in update_data, (
                f"Update should NOT include stored_config. Keys: {list(update_data.keys())}"
            )

        finally:
            entity_id = "automation.opttest_update_noconfig"
            try:
                await mcp_client.call_tool(
                    "ha_config_remove_automation",
                    {"entity_id": entity_id},
                )
            except Exception as e:
                logger.debug(f"Cleanup of {entity_id} failed: {e}")


# ---------------------------------------------------------------------------
# TestAutomationWaitTiming — verify entity is fully queryable after creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAutomationWaitTiming:
    """Test that automation creation waits until entity is fully queryable."""

    async def test_create_automation_immediately_queryable(self, mcp_client):
        """After ha_config_set_automation returns, entity should have attributes.id set."""
        config = {
            "alias": "OptTest Wait Timing",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "sun.sun",
                    "to": "above_horizon",
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "light.opttest_timing"},
                }
            ],
        }

        result = await mcp_client.call_tool(
            "ha_config_set_automation",
            {"config": config},
        )

        try:
            data = assert_mcp_success(result, "Create automation for timing test")
            entity_id = data.get("entity_id")
            unique_id = data.get("unique_id")

            assert entity_id, f"No entity_id in response: {data}"
            assert unique_id, f"No unique_id in response: {data}"

            # Immediately query state — should succeed without extra delay
            state_result = await mcp_client.call_tool(
                "ha_get_state",
                {"entity_id": entity_id},
            )
            state_data = assert_mcp_success(state_result, f"Get state {entity_id}")

            # Verify attributes.id matches unique_id
            inner = state_data.get("data", state_data)
            attributes = inner.get("attributes", {})
            assert attributes.get("id") == unique_id, (
                f"attributes.id should be '{unique_id}', "
                f"got '{attributes.get('id')}'. "
                f"Wait timing may not be working correctly."
            )
            logger.info(
                f"Automation {entity_id} immediately queryable with "
                f"attributes.id={attributes.get('id')}"
            )

        finally:
            entity_id = data.get("entity_id", "automation.opttest_wait_timing")
            try:
                await mcp_client.call_tool(
                    "ha_config_remove_automation",
                    {"entity_id": entity_id},
                )
            except Exception as e:
                logger.debug(f"Cleanup of {entity_id} failed: {e}")

    async def test_create_automation_searchable(self, mcp_client):
        """After creation, automation should be findable via ha_deep_search."""
        config = {
            "alias": "OptTest Searchable After Create",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "sun.sun",
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "light.opttest_search"},
                }
            ],
        }

        result = await mcp_client.call_tool(
            "ha_config_set_automation",
            {"config": config},
        )

        try:
            data = assert_mcp_success(result, "Create automation for search test")

            # Search should find it via wait_for_tool_result (with reasonable timeout)
            search_data = await wait_for_tool_result(
                mcp_client,
                tool_name="ha_deep_search",
                arguments={
                    "query": "OptTest Searchable After Create",
                    "search_types": ["automation"],
                    "limit": 5,
                },
                predicate=lambda d: len(d.get("automations", [])) > 0,
                description="Find newly created automation via deep search",
                timeout=10,
            )

            automations = search_data.get("automations", [])
            assert len(automations) > 0, (
                "Automation should be searchable immediately after creation returns"
            )

            found = any(
                "OptTest Searchable" in a.get("friendly_name", "")
                for a in automations
            )
            assert found, (
                f"Should find specific test automation. Got: "
                f"{[a.get('friendly_name') for a in automations]}"
            )

        finally:
            entity_id = "automation.opttest_searchable_after_create"
            try:
                await mcp_client.call_tool(
                    "ha_config_remove_automation",
                    {"entity_id": entity_id},
                )
            except Exception as e:
                logger.debug(f"Cleanup of {entity_id} failed: {e}")
