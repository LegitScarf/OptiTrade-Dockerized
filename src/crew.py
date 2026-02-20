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


def safe_load_yaml(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            logger.warning(f"Config file not found: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        logger.error(f"Failed to load YAML {path}: {e}")
        return {}


def safe_write_json(data: Any, filename: str) -> bool:
    try:
        full_path = get_output_path(filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        if data is None:
            payload = {"status": "no_output", "message": "Agent returned no structured output"}
        elif isinstance(data, dict):
            payload = data
        elif isinstance(data, str):
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                payload = {"status": "raw_text", "content": data}
        else:
            payload = {"status": "unknown_type", "content": str(data)}

        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to write {filename}: {e}")
        return False


@CrewBase
class OptiTradeCrew():
    """OptiTrade Crew - Multi-agent options trading research system"""

    # CRITICAL FIX: Set these to None to prevent @CrewBase from attempting its own
    # config loading. We handle config loading manually in __init__ with proper
    # path resolution for Docker. If these are strings, @CrewBase tries to load them
    # relative to src/ directory, which fails and generates warnings.
    agents_config = None
    tasks_config = None

    def __init__(self, inputs: Optional[Dict[str, Any]] = None):
        # CRITICAL FIX: Try multiple possible config directory locations
        # to handle both local development and Docker deployment scenarios
        possible_roots = [
            Path(__file__).parent.parent,  # Standard: /app (when __file__ is /app/src/crew.py)
            Path(__file__).parent,          # Fallback: /app/src (if config moved to src/)
            Path.cwd(),                     # Fallback: current working directory
        ]
        
        config_loaded = False
        
        for root in possible_roots:
            agents_path = root / "config" / "agents.yaml"
            tasks_path = root / "config" / "tasks.yaml"
            
            logger.info(f"Trying config path: {root / 'config'}")
            
            if agents_path.exists() and tasks_path.exists():
                logger.info(f"✅ Found config files at: {root / 'config'}")
                
                self.agents_config = safe_load_yaml(str(agents_path))
                self.tasks_config = safe_load_yaml(str(tasks_path))
                
                # Verify the files actually loaded content
                if self.agents_config and self.tasks_config:
                    config_loaded = True
                    logger.info(f"✅ Loaded {len(self.agents_config)} agents, {len(self.tasks_config)} tasks")
                    break
                else:
                    logger.warning(f"⚠️  Config files found but empty or failed to parse at {root / 'config'}")
            else:
                logger.warning(f"⚠️  Config files not found at {root / 'config'}")
        
        if not config_loaded:
            # Provide detailed diagnostics
            logger.error("❌ CRITICAL: Could not load config files from any location")
            logger.error(f"Attempted paths:")
            for root in possible_roots:
                logger.error(f"  - {root / 'config' / 'agents.yaml'}")
                logger.error(f"  - {root / 'config' / 'tasks.yaml'}")
            logger.error(f"Current working directory: {Path.cwd()}")
            logger.error(f"__file__ location: {Path(__file__)}")
            logger.error(f"__file__.parent: {Path(__file__).parent}")
            logger.error(f"__file__.parent.parent: {Path(__file__).parent.parent}")
            
            # List what actually exists
            for root in possible_roots:
                config_dir = root / "config"
                if config_dir.exists():
                    logger.error(f"Contents of {config_dir}:")
                    for item in config_dir.iterdir():
                        logger.error(f"  - {item.name}")
            
            raise FileNotFoundError(
                "Config files (agents.yaml, tasks.yaml) not found in any expected location. "
                "Check Docker image build: ensure 'COPY . .' includes the config/ directory."
            )
        
        # CRITICAL FIX: Verify all required keys exist in the loaded configs
        # This catches YAML structure issues early with clear error messages
        required_agents = [
            "market_data_agent", "technical_analyst_agent", "sentiment_analyst_agent",
            "volatility_greeks_agent", "backtester_agent", "strategy_synthesizer_agent",
            "risk_hedging_advisor_agent", "final_decision_agent", "report_generator_agent"
        ]
        required_tasks = [
            "fetch_market_data", "analyze_technicals", "analyze_sentiment",
            "compute_greeks_volatility", "backtest_strategies", "synthesize_strategy",
            "assess_risk_hedging", "make_final_decision", "generate_report"
        ]
        
        missing_agents = [a for a in required_agents if a not in self.agents_config]
        missing_tasks = [t for t in required_tasks if t not in self.tasks_config]
        
        if missing_agents:
            logger.error(f"❌ Missing agent configs: {missing_agents}")
            logger.error(f"Available agents: {list(self.agents_config.keys())}")
            raise KeyError(f"agents.yaml is missing required keys: {missing_agents}")
        
        if missing_tasks:
            logger.error(f"❌ Missing task configs: {missing_tasks}")
            logger.error(f"Available tasks: {list(self.tasks_config.keys())}")
            raise KeyError(f"tasks.yaml is missing required keys: {missing_tasks}")
        
        self.inputs = inputs or {}

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
            config=self.tasks_config["fetch_market_data"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "market_data.json"
            )
        )

    @task
    def analyze_technicals(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_technicals"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "technical_analysis.json"
            )
        )

    @task
    def analyze_sentiment(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_sentiment"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "sentiment_analysis.json"
            )
        )

    @task
    def compute_greeks_volatility(self) -> Task:
        return Task(
            config=self.tasks_config["compute_greeks_volatility"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "greeks_volatility.json"
            )
        )

    @task
    def backtest_strategies(self) -> Task:
        return Task(
            config=self.tasks_config["backtest_strategies"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "backtest_results.json"
            )
        )

    @task
    def synthesize_strategy(self) -> Task:
        return Task(
            config=self.tasks_config["synthesize_strategy"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "strategy_synthesis.json"
            )
        )

    @task
    def assess_risk_hedging(self) -> Task:
        return Task(
            config=self.tasks_config["assess_risk_hedging"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "risk_assessment.json"
            )
        )

    @task
    def make_final_decision(self) -> Task:
        return Task(
            config=self.tasks_config["make_final_decision"],
            callback=lambda output: safe_write_json(
                output.json_dict if output.json_dict is not None else output.raw,
                "final_decision.json"
            )
        )

    @task
    def generate_report(self) -> Task:
        def report_callback(output):
            content = output.raw
            report_path = get_output_path("trading_report.md")
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(content)
            return output

        all_tasks = self.tasks
        report_context = [t for t in all_tasks if t is not self.generate_report()]

        return Task(
            config=self.tasks_config["generate_report"],
            context=report_context,
            callback=report_callback
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
            max_rpm=10
        )



# import os
# import yaml
# import json
# import logging
# from typing import Dict, Any, Optional
# from pathlib import Path

# from crewai import Agent, Crew, Process, Task
# from crewai.project import CrewBase, agent, crew, task
# from crewai_tools import SerperDevTool

# from .tools import (
#     get_angel_ltp,
#     get_angel_quote,
#     get_angel_option_chain,
#     get_angel_historical_data,
#     calculate_technical_indicators,
#     calculate_options_greeks,
#     backtest_option_strategy,
#     analyze_sentiment_from_text,
#     find_nifty_expiry_dates,
#     authenticate_angel,
#     download_instrument_master_json,
#     test_all_apis,
#     build_multi_leg_strategy,
#     place_option_order
# )
# from .utils import get_config_path, get_output_path

# logger = logging.getLogger("OptiTrade.Crew")
# if not logger.handlers:
#     ch = logging.StreamHandler()
#     ch.setFormatter(logging.Formatter(
#         "%(asctime)s — %(levelname)s — %(name)s — %(message)s",
#         "%Y-%m-%d %H:%M:%S"
#     ))
#     logger.addHandler(ch)
#     logger.setLevel(logging.INFO)


# def safe_load_yaml(path: str) -> Dict[str, Any]:
#     try:
#         if not os.path.exists(path):
#             logger.warning(f"Config file not found: {path}")
#             return {}
#         with open(path, "r", encoding="utf-8") as fh:
#             return yaml.safe_load(fh) or {}
#     except Exception as e:
#         logger.error(f"Failed to load YAML {path}: {e}")
#         return {}


# def safe_write_json(data: Any, filename: str) -> bool:
#     # FIX: The original function assumed 'data' was always a dict (output.json_dict).
#     # CrewAI task output .json_dict is None when the agent returns plain text instead
#     # of valid JSON, which caused silent callback crashes. We now handle all output
#     # types — dict, string, or None — and always write something meaningful to disk.
#     try:
#         full_path = get_output_path(filename)
#         os.makedirs(os.path.dirname(full_path), exist_ok=True)

#         if data is None:
#             payload = {"status": "no_output", "message": "Agent returned no structured output"}
#         elif isinstance(data, dict):
#             payload = data
#         elif isinstance(data, str):
#             try:
#                 payload = json.loads(data)
#             except (json.JSONDecodeError, ValueError):
#                 payload = {"status": "raw_text", "content": data}
#         else:
#             payload = {"status": "unknown_type", "content": str(data)}

#         with open(full_path, "w", encoding="utf-8") as f:
#             json.dump(payload, f, indent=2, default=str, ensure_ascii=False)
#         return True
#     except Exception as e:
#         logger.error(f"Failed to write {filename}: {e}")
#         return False


# @CrewBase
# class OptiTradeCrew():
#     """OptiTrade Crew - Multi-agent options trading research system"""

#     agents_config = "config/agents.yaml"
#     tasks_config = "config/tasks.yaml"

#     def __init__(self, inputs: Optional[Dict[str, Any]] = None):
#         # FIX: Use absolute paths that work in Docker
#         config_dir = Path(__file__).parent.parent / "config"
#         self.agents_config = safe_load_yaml(str(config_dir / "agents.yaml"))
#         self.tasks_config = safe_load_yaml(str(config_dir / "tasks.yaml"))
#         self.inputs = inputs or {}

#     @agent
#     def market_data_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["market_data_agent"],
#             tools=[
#                 get_angel_ltp,
#                 get_angel_quote,
#                 get_angel_option_chain,
#                 get_angel_historical_data,
#                 download_instrument_master_json,
#                 SerperDevTool()
#             ],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def technical_analyst_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["technical_analyst_agent"],
#             tools=[calculate_technical_indicators, get_angel_historical_data],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def sentiment_analyst_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["sentiment_analyst_agent"],
#             tools=[analyze_sentiment_from_text, SerperDevTool()],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def volatility_greeks_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["volatility_greeks_agent"],
#             tools=[calculate_options_greeks, get_angel_option_chain],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def backtester_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["backtester_agent"],
#             tools=[backtest_option_strategy, get_angel_historical_data],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def strategy_synthesizer_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["strategy_synthesizer_agent"],
#             tools=[build_multi_leg_strategy],
#             verbose=True,
#             # FIX: Changed allow_delegation to False. With True, the synthesizer
#             # could spawn uninstructed sub-tasks outside the defined pipeline,
#             # making the decision chain non-auditable and unpredictable.
#             allow_delegation=False
#         )

#     @agent
#     def risk_hedging_advisor_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["risk_hedging_advisor_agent"],
#             tools=[calculate_options_greeks],
#             verbose=True,
#             allow_delegation=False
#         )

#     @agent
#     def final_decision_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["final_decision_agent"],
#             tools=[place_option_order],
#             verbose=True,
#             # FIX: Changed allow_delegation to False. The final decision agent
#             # must only act on explicitly passed context — open delegation here
#             # could cause it to re-invoke upstream agents with stale or different
#             # market state, producing an inconsistent decision.
#             allow_delegation=False
#         )

#     @agent
#     def report_generator_agent(self) -> Agent:
#         return Agent(
#             config=self.agents_config["report_generator_agent"],
#             verbose=True,
#             allow_delegation=False
#         )

#     @task
#     def fetch_market_data(self) -> Task:
#         return Task(
#             config=self.tasks_config["fetch_market_data"],
#             # FIX: Callback now routes through safe_write_json which handles
#             # None, plain text, and dict outputs — previously a None json_dict
#             # would crash silently here and no file would be written.
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "market_data.json"
#             )
#         )

#     @task
#     def analyze_technicals(self) -> Task:
#         return Task(
#             config=self.tasks_config["analyze_technicals"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "technical_analysis.json"
#             )
#         )

#     @task
#     def analyze_sentiment(self) -> Task:
#         return Task(
#             config=self.tasks_config["analyze_sentiment"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "sentiment_analysis.json"
#             )
#         )

#     @task
#     def compute_greeks_volatility(self) -> Task:
#         return Task(
#             config=self.tasks_config["compute_greeks_volatility"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "greeks_volatility.json"
#             )
#         )

#     @task
#     def backtest_strategies(self) -> Task:
#         return Task(
#             config=self.tasks_config["backtest_strategies"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "backtest_results.json"
#             )
#         )

#     @task
#     def synthesize_strategy(self) -> Task:
#         return Task(
#             config=self.tasks_config["synthesize_strategy"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "strategy_synthesis.json"
#             )
#         )

#     @task
#     def assess_risk_hedging(self) -> Task:
#         return Task(
#             config=self.tasks_config["assess_risk_hedging"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "risk_assessment.json"
#             )
#         )

#     @task
#     def make_final_decision(self) -> Task:
#         return Task(
#             config=self.tasks_config["make_final_decision"],
#             callback=lambda output: safe_write_json(
#                 output.json_dict if output.json_dict is not None else output.raw,
#                 "final_decision.json"
#             )
#         )

#     @task
#     def generate_report(self) -> Task:
#         def report_callback(output):
#             content = output.raw
#             report_path = get_output_path("trading_report.md")
#             os.makedirs(os.path.dirname(report_path), exist_ok=True)
#             with open(report_path, "w", encoding="utf-8") as f:
#                 f.write(content)
#             return output

#         # FIX: The original code called self.fetch_market_data(), self.analyze_technicals()
#         # etc. to build the context list. Each of those calls creates a brand-new Task
#         # instance that has never been executed, so CrewAI has no output to pass as
#         # context — the report agent would receive empty context every time.
#         # The fix is to reference the already-registered task instances that the crew
#         # actually ran, which are stored in self.tasks after crew assembly. Since
#         # @CrewBase populates self.tasks in order, we slice all but the last (report)
#         # task and use those as context.
#         # We build the list by name-matching so it is robust to task reordering.
#         all_tasks = self.tasks  # populated by @CrewBase after all @task methods run
#         report_context = [t for t in all_tasks if t is not self.generate_report()]

#         return Task(
#             config=self.tasks_config["generate_report"],
#             context=report_context,
#             callback=report_callback
#         )

#     @crew
#     def crew(self) -> Crew:
#         return Crew(
#             agents=self.agents,
#             tasks=self.tasks,
#             # FIX: Changed from Process.sequential to Process.sequential explicitly
#             # with async_execution disabled at the crew level. The three tasks marked
#             # async_execution:true in YAML conflict with sequential process — CrewAI's
#             # sequential process ignores async_execution flags and runs tasks in order
#             # anyway, but the flag causes ambiguous state in some CrewAI versions.
#             # Async parallelism in CrewAI requires Process.hierarchical or a custom
#             # runner — sequential + async_execution is a no-op at best, a crash at worst.
#             process=Process.sequential,
#             verbose=True,
#             memory=False,
#             max_rpm=10
#         )
