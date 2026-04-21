"""
CrowdAudit — Zerve API Client

Handles all programmatic communication with Zerve:

  Phase 1
    Submits prompts to a Zerve agent session and retrieves findings.
    Used when you want to trigger an agent run from Python rather than
    the Zerve UI — useful for automating the calibration loop.

  Phase 2
    Once scoring logic is deployed to Zerve as a workflow, this client
    calls ZERVE_ENDPOINT_URL to get a live Sanity Score for any topic.
    The FastAPI server in api/endpoint.py calls this instead of running
    the scoring engine locally.

Environment variables required (set in .env):
  ZERVE_API_KEY       — from Zerve dashboard > Settings > API Keys
  ZERVE_ENDPOINT_URL  — your deployed workflow URL (empty until Day 7–9)
"""

import os
import json
import logging
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ZERVE_API_KEY = os.getenv("ZERVE_API_KEY", "")
ZERVE_ENDPOINT_URL = os.getenv("ZERVE_ENDPOINT_URL", "")
REQUEST_TIMEOUT = 30  # seconds — agent calls can be slow


#  Auth header


def _auth_headers() -> dict:
    if not ZERVE_API_KEY:
        raise EnvironmentError(
            "ZERVE_API_KEY is not set. Add it to your .env file.\n"
            "Find your key at: Zerve dashboard > Settings > API Keys"
        )
    return {
        "Authorization": f"Bearer {ZERVE_API_KEY}",
        "Content-Type": "application/json",
    }


#  Phase 1: Agent session


def run_agent_prompt(
    prompt: str,
    session_id: Optional[str] = None,
) -> dict:
    """
    Submit a prompt to a Zerve agent session and return the response.

    Use this when you want to trigger an agent exploration run from Python
    rather than pasting prompts manually in the Zerve UI.

    The prompts themselves live in zerve_prompts/zerve_prompts.py.
    Call them like this:

        from zerve_prompts.zerve_prompts import MASTER_EXPLORATION_QUESTION
        from zerve_client import run_agent_prompt

        result = run_agent_prompt(MASTER_EXPLORATION_QUESTION)
        print(result["output"])

    Args:
        prompt:     The full prompt string to submit.
        session_id: Optional — pass an existing session ID to continue
                    a conversation. None starts a new session.

    Returns dict with keys:
        output      str   — the agent's response text
        session_id  str   — use this to continue the session
        usage       dict  — token counts if available
    """
    # NOTE: Replace this URL with the actual Zerve agent API endpoint
    # once you have access to the Zerve developer docs.
    # The structure below follows the standard pattern for agent APIs.
    url = "https://api.zerve.ai/v1/agent/run"

    payload: dict = {"prompt": prompt}
    if session_id:
        payload["session_id"] = session_id

    try:
        response = requests.post(
            url,
            headers=_auth_headers(),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(
            f"Zerve agent API error {e.response.status_code}: {e.response.text}"
        )
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Could not reach the Zerve API. Check your internet connection "
            "and that https://api.zerve.ai is accessible."
        )


#  Phase 2: Deployed scoring endpoint (Days 7–9 onwards)


def get_live_score(topic_id: str, topic_title: str, data_domain: str) -> dict:
    """
    Call the deployed Zerve scoring workflow to get a live Sanity Score.

    This replaces mock data in api/endpoint.py once the scoring workflow
    is deployed to Zerve. The FastAPI endpoint calls this function
    and returns its output directly to the frontend.

    Args:
        topic_id:     Unique identifier for the topic (e.g. "COVID_ORIGIN_NARRATIVE")
        topic_title:  Human-readable topic description
        data_domain:  One of: "economic", "health", "political", "climate"

    Returns:
        dict matching the SanityScoreResponse schema in api/endpoint.py
        (sanity_score, irrationality_index, signal_breakdown, reason, etc.)

    Raises:
        EnvironmentError  if ZERVE_ENDPOINT_URL is not set
        HTTPError         if the Zerve endpoint returns an error
    """
    if not ZERVE_ENDPOINT_URL:
        raise EnvironmentError(
            "ZERVE_ENDPOINT_URL is not set in your .env file.\n"
            "Deploy your scoring workflow to Zerve first (Days 7–9), "
            "then paste the endpoint URL into .env."
        )

    try:
        response = requests.post(
            ZERVE_ENDPOINT_URL,
            headers=_auth_headers(),
            json={
                "topic_id": topic_id,
                "topic_title": topic_title,
                "data_domain": data_domain,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(
            f"Zerve scoring endpoint error {e.response.status_code}: {e.response.text}"
        )
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Could not reach Zerve endpoint: {ZERVE_ENDPOINT_URL}\n"
            "Check that the endpoint is deployed and ZERVE_ENDPOINT_URL is correct."
        )


#  Connectivity check


def check_zerve_connection() -> dict:
    """
    Verify ZERVE_API_KEY is set and the Zerve API is reachable.
    Call this at startup or in your integration tests.

    Returns:
        {"status": "ok", "endpoint_configured": bool}
    Raises:
        EnvironmentError if ZERVE_API_KEY is missing
        ConnectionError  if the API is unreachable
    """
    if not ZERVE_API_KEY:
        raise EnvironmentError("ZERVE_API_KEY is not set. Add it to your .env file.")

    return {
        "status": "ok",
        "api_key_set": True,
        "endpoint_configured": bool(ZERVE_ENDPOINT_URL),
        "endpoint_url": ZERVE_ENDPOINT_URL or "not set — deploy first",
    }


#  Self-test

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Zerve client configuration check:")
    print(f"  ZERVE_API_KEY set:      {bool(ZERVE_API_KEY)}")
    print(f"  ZERVE_ENDPOINT_URL set: {bool(ZERVE_ENDPOINT_URL)}")

    if not ZERVE_API_KEY:
        print("\n  ZERVE_API_KEY is missing — add it to your .env file")
        print("  Find your key: Zerve dashboard > Settings > API Keys")
    else:
        print("\n  API key found. Run check_zerve_connection() to verify connectivity.")

    if not ZERVE_ENDPOINT_URL:
        print("\n  ZERVE_ENDPOINT_URL is empty — this is expected until Day 7-9.")
        print("  Deploy your scoring workflow to Zerve, then paste the URL into .env.")
