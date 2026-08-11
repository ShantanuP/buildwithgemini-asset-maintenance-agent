# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from .a2ui_utils import a2ui_callback
from .tools import (
    calculate_asset_metrics,
    query_asset_docs,
    query_maintenance_db,
)

MODEL = "gemini-3.6-flash"

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Asset Maintenance Agent, an expert building operations and equipment management AI assistant. "
        "You help building managers and field technicians diagnose equipment issues, query preventive and "
        "reactive maintenance records, and reference technical specification manuals for building assets."
    ),
    workflow_description=(
        "1. Identify the building asset (e.g., HVAC-03, Chiller-01, Elevator-02).\n"
        "2. Query the maintenance database for past preventive/reactive service logs and repair costs.\n"
        "3. Search technical documentation manuals for operating specs, pressure limits, and troubleshooting trees.\n"
        "4. Calculate maintenance metrics and render concise asset cards and work order summaries using A2UI."
    ),
    ui_description=(
        "Keep A2UI cards concise and flat: ONE Card > ONE Column > 4 to 6 Text rows summarizing "
        "key asset metrics (e.g., Asset Name, Location, Status, Total Spend, Recent Log Date). "
        "Do NOT attempt to put every individual log entry into a massive A2UI component tree. "
        "Provide full itemized maintenance histories and technical spec excerpts in standard markdown text. "
        "Never nest a Card inside a Card. Use ONLY Card, Column, Row, Text, and Image. "
        "Output ONLY raw valid A2UI JSON for the summary card."
    ),
    include_schema=True,
    include_examples=True,
)

# Specialist Subagents
db_agent = Agent(
    name="db_agent",
    model=Gemini(model=MODEL, retry_options=types.HttpRetryOptions(attempts=3)),
    instruction="Specialist for querying asset details, preventive service logs, and reactive repair records from the SQLite database.",
    tools=[query_maintenance_db],
)

docs_agent = Agent(
    name="docs_agent",
    model=Gemini(model=MODEL, retry_options=types.HttpRetryOptions(attempts=3)),
    instruction="Specialist for searching technical specification manuals, operating parameters, and troubleshooting guides in the documentation folder.",
    tools=[query_asset_docs],
)

analytics_agent = Agent(
    name="analytics_agent",
    model=Gemini(model=MODEL, retry_options=types.HttpRetryOptions(attempts=3)),
    instruction="Specialist for calculating total maintenance spend, event counts, and cost metrics.",
    tools=[calculate_asset_metrics],
)

# Root Orchestrator Agent
root_agent = Agent(
    name="root_agent",
    model=Gemini(model=MODEL, retry_options=types.HttpRetryOptions(attempts=3)),
    instruction=f"{a2ui_instruction}\n\nYou can delegate specialized tasks to db_agent, docs_agent, and analytics_agent or call tools directly.",
    tools=[
        query_maintenance_db,
        query_asset_docs,
        calculate_asset_metrics,
    ],
    sub_agents=[db_agent, docs_agent, analytics_agent],
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="asset-maintenance-agent",
)
