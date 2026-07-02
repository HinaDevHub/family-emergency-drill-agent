# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import pytest
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent

# ---------------------------------------------------------------------------
# Per the ADK Agent Builder Playbook:
#   "Do NOT automate browser UI testing or run automated multi-turn
#    integration test scripts that query real LLM endpoints. This rapidly
#    depletes the user's free tier quota (raising 429 RESOURCE_EXHAUSTED
#    errors)."
#
# This test is therefore marked MANUAL_ONLY and skipped in automated CI.
# To run it manually, set the env var: RUN_LLM_INTEGRATION=1
#   e.g.:  RUN_LLM_INTEGRATION=1 uv run pytest tests/integration/test_agent.py -v
# ---------------------------------------------------------------------------
RUN_LLM_INTEGRATION = os.environ.get("RUN_LLM_INTEGRATION", "").strip() == "1"

manual_only = pytest.mark.skipif(
    not RUN_LLM_INTEGRATION,
    reason=(
        "Live LLM integration test — skipped in automated runs to avoid quota "
        "exhaustion (429/503). Set RUN_LLM_INTEGRATION=1 to run manually."
    ),
)


@manual_only
def test_agent_stream() -> None:
    """
    Manual integration test for the agent stream functionality.
    Verifies the full agent workflow returns valid streaming responses.

    Run manually with:
        RUN_LLM_INTEGRATION=1 uv run pytest tests/integration/test_agent.py -v
    """
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name="test",
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text="There is a fire in my kitchen! Smoke is spreading fast."
            )
        ],
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0, "Expected at least one event from the agent"

    has_text_content = any(
        event.content
        and event.content.parts
        and any(part.text for part in event.content.parts)
        for event in events
    )
    assert has_text_content, "Expected at least one event with text content"
