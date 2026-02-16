import os
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from uyuni_ai_agent.llm_provider import get_llm
from uyuni_ai_agent.schemas import AnalysisResult
from uyuni_ai_agent.tools.process_tools import get_top_memory_processes, get_top_cpu_processes
from uyuni_ai_agent.tools.disk_tools import get_disk_usage, find_large_files
from uyuni_ai_agent.tools.service_tools import get_service_status, get_service_logs
from uyuni_ai_agent.tools.network_tools import check_connectivity, get_listening_ports


# All Salt inspection tools available to the agent
ALL_TOOLS = [
    get_top_memory_processes,
    get_top_cpu_processes,
    get_disk_usage,
    find_large_files,
    get_service_status,
    get_service_logs,
    check_connectivity,
    get_listening_ports,
]


def load_prompt(template_name, **kwargs):
    """Load a prompt template from the prompts/ directory and fill in variables."""
    prompts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts"
    )
    template_path = os.path.join(prompts_dir, template_name)
    with open(template_path, "r") as f:
        template = f.read()
    return template.format(**kwargs)


def get_prompt_for_anomaly(anomaly, metrics):
    """Pick the right prompt template based on the anomaly type."""
    template_map = {
        "memory": "high_ram.md",
        "cpu": "high_cpu.md",
        "disk": "disk_full.md",
    }
    template_name = template_map.get(anomaly.metric_name, "high_ram.md")
    return load_prompt(
        template_name,
        minion_id=anomaly.minion_id,
        instance=anomaly.minion_id,
        current_value=f"{anomaly.current_value:.1f}",
        threshold=f"{anomaly.threshold:.1f}",
        severity=anomaly.severity.value,
        metrics=str(metrics),
    )


def investigate(anomaly, metrics):
    """Run the ReAct agent to investigate an anomaly.

    Uses a two-step approach:
    1. ReAct agent gathers context via Salt tools and reasons about root cause
    2. The raw analysis is parsed into an AnalysisResult schema via
       with_structured_output() for reliable field extraction

    Args:
        anomaly: an Anomaly dataclass from anomaly_detector
        metrics: dict of current Prometheus metrics

    Returns:
        AnalysisResult: structured analysis with root_cause, evidence,
                        remediation, urgency, and description fields
    """
    llm = get_llm()

    # Load prompts
    system_prompt = load_prompt("system_prompt.md")
    scenario_prompt = get_prompt_for_anomaly(anomaly, metrics)

    # Step 1: ReAct agent investigates using Salt tools
    agent = create_react_agent(llm, ALL_TOOLS)
    result = agent.invoke({
        "messages": [
            SystemMessage(content=system_prompt),
            ("human", scenario_prompt),
        ]
    })

    raw_analysis = result["messages"][-1].content

    # Step 2: Parse into structured schema
    structured_llm = llm.with_structured_output(AnalysisResult)
    try:
        analysis = structured_llm.invoke(
            f"Parse the following server analysis into the required JSON schema. "
            f"Extract the root cause, evidence, remediation steps, urgency, "
            f"and a full description.\n\n{raw_analysis}"
        )
        return analysis
    except Exception as e:
        # Fallback: wrap raw text in the schema manually
        print(f"[WARN] Structured parsing failed: {e}, using fallback")
        return AnalysisResult(
            root_cause="See description for details",
            evidence=[],
            remediation=["Manual investigation required"],
            urgency="medium",
            description=raw_analysis,
        )
