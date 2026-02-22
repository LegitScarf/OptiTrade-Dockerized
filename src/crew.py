import os
import yaml
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from .tools import (
    get_angel_ltp,
    get_angel_quote,
    get_angel_option_chain,
    get_angel_historical_data,
    calculate_technical_indicators,
    calculate_options_greeks,
    backtest_option_strategy,
    analyze_sentiment_from_text,
    find_nifty_expiry_dates,
    authenticate_angel,
    download_instrument_master_json,
    test_all_apis,
    build_multi_leg_strategy,
    place_option_order
)
from .utils import get_config_path, get_output_path

logger = logging.getLogger("OptiTrade.Crew")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        "%(asctime)s — %(levelname)s — %(name)s — %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

# FIX: config/ is at project root /app/config/, two levels up from this file
# (/app/src/crew.py → /app/src/ → /app/). Using absolute paths here ensures
# CrewAI finds agents.yaml and tasks.yaml regardless of the process cwd.
_CONFIG_DIR = Path(__file__).parent.parent / "config"


@CrewBase
class OptiTradeCrew():

    agents_config = str(_CONFIG_DIR / "agents.yaml")
    tasks_config  = str(_CONFIG_DIR / "tasks.yaml")

    @agent
    def market_data_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["market_data_agent"],
            tools=[
                get_angel_ltp,
                get_angel_quote,
                get_angel_option_chain,
                get_angel_historical_data,
                download_instrument_master_json,
                SerperDevTool()
            ],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def technical_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["technical_analyst_agent"],
            tools=[calculate_technical_indicators, get_angel_historical_data],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def sentiment_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["sentiment_analyst_agent"],
            tools=[analyze_sentiment_from_text, SerperDevTool()],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def volatility_greeks_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["volatility_greeks_agent"],
            tools=[calculate_options_greeks, get_angel_option_chain],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def backtester_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["backtester_agent"],
            tools=[backtest_option_strategy, get_angel_historical_data],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def strategy_synthesizer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["strategy_synthesizer_agent"],
            tools=[build_multi_leg_strategy],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def risk_hedging_advisor_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_hedging_advisor_agent"],
            tools=[calculate_options_greeks],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def final_decision_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["final_decision_agent"],
            tools=[place_option_order],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def report_generator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["report_generator_agent"],
            verbose=True,
            allow_delegation=False
        )

    @task
    def fetch_market_data(self) -> Task:
        return Task(
            config=self.tasks_config['fetch_market_data']
        )

    @task
    def analyze_technicals(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_technicals']
        )

    @task
    def analyze_sentiment(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_sentiment']
        )

    @task
    def compute_greeks_volatility(self) -> Task:
        return Task(
            config=self.tasks_config['compute_greeks_volatility']
        )

    @task
    def backtest_strategies(self) -> Task:
        return Task(
            config=self.tasks_config['backtest_strategies']
        )

    @task
    def synthesize_strategy(self) -> Task:
        return Task(
            config=self.tasks_config['synthesize_strategy']
        )

    @task
    def assess_risk_hedging(self) -> Task:
        return Task(
            config=self.tasks_config['assess_risk_hedging']
        )

    @task
    def make_final_decision(self) -> Task:
        return Task(
            config=self.tasks_config['make_final_decision']
        )

    @task
    def generate_report(self) -> Task:
        return Task(
            config=self.tasks_config['generate_report']
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
            max_rpm=30,
            full_output=True
        )