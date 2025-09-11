# Google ADK (Agent Development Kit) - Comprehensive Guide

## Table of Contents
1. [What is ADK?](#what-is-adk)
2. [Core Concepts](#core-concepts)
3. [Installation & Setup](#installation--setup)
4. [Agent Types](#agent-types)
5. [Building Agents](#building-agents)
6. [Tools & Integration](#tools--integration)
7. [Workflows & Orchestration](#workflows--orchestration)
8. [Best Practices](#best-practices)
9. [Migration Guide](#migration-guide)
10. [Advanced Features](#advanced-features)

## What is ADK?

Google's **Agent Development Kit (ADK)** is an open-source, code-first Python toolkit introduced at Cloud NEXT 2025. It simplifies the development of AI agents and multi-agent systems with a focus on making agent development feel like traditional software development.

### Key Characteristics
- **Model-agnostic**: Works with Gemini, Vertex AI Model Garden, and LiteLLM providers
- **Deployment-agnostic**: Local, Vertex AI Agent Engine, Cloud Run, Docker
- **Framework-compatible**: Integrates with LangChain, CrewAI, and other frameworks
- **Production-ready**: Built for enterprise-grade deployments

### Philosophy
"Making agent development feel like software development" - ADK eliminates friction and provides systematic approaches to building agents from simple tasks to complex workflows.

## Core Concepts

### 1. Agents as First-Class Citizens
Agents in ADK are autonomous units that can:
- Process inputs and generate outputs
- Use tools to interact with external systems
- Collaborate with other agents
- Maintain state and memory

### 2. Structured Responses
All tools and agents return structured dictionary responses:
```python
{
    "status": "success" | "error",
    "data": <result_data>,
    "message": "Human-readable message",
    "error_message": "Error details if failed"
}
```

### 3. Hierarchical Composition
Agents can have sub-agents, creating hierarchical structures:
```python
coordinator_agent
├── data_processing_agent
├── analysis_agent
└── reporting_agent
```

### 4. Tool Ecosystem
ADK provides rich tool integration:
- Built-in tools (file I/O, web search, etc.)
- MCP (Model Context Protocol) tools
- Third-party integrations (LangChain, CrewAI)
- Custom tool development

## Installation & Setup

### Basic Installation
```bash
# Stable release (recommended)
pip install google-adk

# Development version
pip install git+https://github.com/google/adk-python.git@main

# With additional providers
pip install google-adk[litellm]  # For non-Google models
```

### Authentication

#### Option 1: Google AI Studio (Simplest)
```python
import os
os.environ['GOOGLE_API_KEY'] = 'your-api-key'
```

#### Option 2: Vertex AI (Enterprise)
```python
os.environ['GOOGLE_CLOUD_PROJECT'] = 'your-project-id'
# Requires gcloud auth or service account
```

#### Option 3: LiteLLM (Multi-provider)
```python
# For Anthropic
os.environ['ANTHROPIC_API_KEY'] = 'your-key'

# For OpenAI
os.environ['OPENAI_API_KEY'] = 'your-key'
```

### Development Tools
```bash
# Start development UI
adk web

# Run in terminal
adk run

# Start API server
adk api_server
```

## Agent Types

### 1. LLM Agents
Language model-powered agents for reasoning and decision-making.

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="research_agent",
    model="gemini-2.0-flash",
    description="Conducts research on topics",
    instruction="You are a research assistant. Be thorough and accurate.",
    tools=[web_search, read_file],
    sub_agents=[]
)
```

**Characteristics**:
- Non-deterministic
- Flexible reasoning
- Natural language understanding
- Best for: Complex decisions, creative tasks, analysis

### 2. Workflow Agents
Control execution flow with predefined patterns.

```python
from google.adk.agents.workflow import Sequential, Parallel, Loop

# Sequential execution
sequential_workflow = Sequential(
    agents=[agent1, agent2, agent3],
    name="data_pipeline"
)

# Parallel execution
parallel_workflow = Parallel(
    agents=[agent1, agent2],
    name="concurrent_tasks"
)

# Loop execution
loop_workflow = Loop(
    agent=processing_agent,
    condition=lambda result: result['continue'],
    max_iterations=10
)
```

**Characteristics**:
- Deterministic
- Predictable flow
- Structured execution
- Best for: Pipelines, batch processing, orchestration

### 3. Custom Agents
Extend BaseAgent for specialized behavior.

```python
from google.adk.agents import BaseAgent

class DataValidatorAgent(BaseAgent):
    def __init__(self, validation_rules):
        super().__init__(name="validator")
        self.rules = validation_rules
    
    def run(self, input_data):
        # Custom validation logic
        errors = []
        for rule in self.rules:
            if not rule.validate(input_data):
                errors.append(rule.error_message)
        
        return {
            "status": "success" if not errors else "error",
            "valid": len(errors) == 0,
            "errors": errors
        }
```

**Characteristics**:
- Fully customizable
- Can be deterministic or non-deterministic
- Direct control over behavior
- Best for: Specialized logic, integrations, performance-critical tasks

## Building Agents

### Basic Agent Structure
```python
from google.adk.agents import Agent
from google.adk.tools import Tool

# Define a tool
def analyze_data(data: str) -> dict:
    """Analyze provided data"""
    # Analysis logic
    return {
        "status": "success",
        "analysis": "Data shows positive trend",
        "confidence": 0.85
    }

# Create agent
analyst = Agent(
    name="data_analyst",
    model="gemini-2.0-flash",
    description="Analyzes data patterns",
    instruction="""
    You are a data analyst. 
    Analyze data thoroughly and provide insights.
    Always return structured results.
    """,
    tools=[analyze_data]
)

# Use agent
result = analyst.run("Analyze sales data for Q4")
```

### Multi-Agent System
```python
from google.adk.agents import LlmAgent

# Specialized agents
researcher = LlmAgent(
    name="researcher",
    model="gemini-2.0-flash",
    description="Researches topics",
    tools=[web_search, read_documents]
)

writer = LlmAgent(
    name="writer",
    model="gemini-2.0-flash",
    description="Writes content",
    tools=[create_document, format_text]
)

editor = LlmAgent(
    name="editor",
    model="gemini-2.0-flash",
    description="Edits and reviews content",
    tools=[check_grammar, improve_style]
)

# Coordinator agent
coordinator = LlmAgent(
    name="content_coordinator",
    model="gemini-2.0-flash",
    description="Coordinates content creation",
    sub_agents=[researcher, writer, editor],
    instruction="""
    Coordinate the content creation process:
    1. Use researcher to gather information
    2. Use writer to create initial draft
    3. Use editor to polish the content
    """
)

# Execute
result = coordinator.run("Create article about quantum computing")
```

### Agent with Memory
```python
from google.adk.agents import LlmAgent
from google.adk.memory import ConversationMemory

memory = ConversationMemory(max_turns=10)

agent = LlmAgent(
    name="assistant",
    model="gemini-2.0-flash",
    description="Personal assistant with memory",
    memory=memory,
    instruction="Remember our conversation context"
)

# Conversation maintains context
agent.run("My name is Alice")
agent.run("What's my name?")  # Will remember "Alice"
```

## Tools & Integration

### Built-in Tools
```python
from google.adk.tools import (
    read_file,
    write_file,
    web_search,
    google_search,
    execute_code
)

agent = LlmAgent(
    name="researcher",
    tools=[web_search, read_file, write_file]
)
```

### Custom Tools
```python
from google.adk.tools import Tool

@Tool
def calculate_metrics(data: list) -> dict:
    """Calculate statistical metrics"""
    import statistics
    
    try:
        return {
            "status": "success",
            "mean": statistics.mean(data),
            "median": statistics.median(data),
            "stdev": statistics.stdev(data)
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e)
        }

# Use in agent
agent = LlmAgent(
    name="statistician",
    tools=[calculate_metrics]
)
```

### LangChain Integration
```python
from langchain_community.tools import TavilySearchResults
from google.adk.tools.langchain_tool import LangchainTool

# Wrap LangChain tool
langchain_tool = TavilySearchResults(api_key="key")
adk_tool = LangchainTool(tool=langchain_tool)

agent = LlmAgent(
    name="searcher",
    tools=[adk_tool]
)
```

### CrewAI Integration
```python
from crewai_tools import WebsiteSearchTool
from google.adk.tools.crewai_tool import CrewaiTool

crewai_tool = WebsiteSearchTool()
adk_tool = CrewaiTool(tool=crewai_tool)

agent = LlmAgent(
    name="web_researcher",
    tools=[adk_tool]
)
```

### MCP Tools
```python
from google.adk.tools.mcp import MCPTool

# Use MCP-compatible tools
mcp_tool = MCPTool(
    server="filesystem",
    operation="read_file"
)

agent = LlmAgent(
    name="file_manager",
    tools=[mcp_tool]
)
```

## Workflows & Orchestration

### Sequential Workflow
```python
from google.adk.agents.workflow import Sequential

workflow = Sequential(
    agents=[
        data_loader,
        data_cleaner,
        data_analyzer,
        report_generator
    ],
    name="data_pipeline",
    description="End-to-end data processing"
)

result = workflow.run(input_data)
```

### Parallel Workflow
```python
from google.adk.agents.workflow import Parallel

workflow = Parallel(
    agents=[
        web_scraper_1,
        web_scraper_2,
        web_scraper_3
    ],
    name="concurrent_scraping",
    aggregation_method="merge"  # or "first", "all"
)

results = workflow.run(urls)
```

### Conditional Workflow
```python
from google.adk.agents.workflow import Conditional

def route_decision(result):
    if result['data_type'] == 'structured':
        return 'sql_processor'
    else:
        return 'nlp_processor'

workflow = Conditional(
    router=route_decision,
    agents={
        'sql_processor': sql_agent,
        'nlp_processor': nlp_agent
    }
)
```

### Loop Workflow
```python
from google.adk.agents.workflow import Loop

workflow = Loop(
    agent=optimization_agent,
    condition=lambda r: r['improvement'] > 0.01,
    max_iterations=100,
    name="iterative_optimizer"
)
```

### Complex Workflow Example
```python
# Combine different workflow types
main_workflow = Sequential([
    # Step 1: Parallel data collection
    Parallel([
        api_fetcher,
        database_reader,
        file_loader
    ]),
    
    # Step 2: Conditional processing
    Conditional(
        router=lambda r: 'processor_type',
        agents={
            'batch': batch_processor,
            'stream': stream_processor
        }
    ),
    
    # Step 3: Iterative refinement
    Loop(
        agent=refiner,
        condition=lambda r: r['quality'] < 0.95,
        max_iterations=5
    ),
    
    # Step 4: Final validation
    validator_agent
])
```

## Best Practices

### 1. Agent Design
- **Single Responsibility**: Each agent should have one clear purpose
- **Clear Instructions**: Provide specific, unambiguous instructions
- **Structured Output**: Always return consistent dictionary structures
- **Error Handling**: Implement robust error handling in tools

### 2. Tool Development
```python
def good_tool(param: str) -> dict:
    """Good tool example with proper structure"""
    try:
        # Validate input
        if not param:
            return {
                "status": "error",
                "error_message": "Parameter required"
            }
        
        # Process
        result = process_data(param)
        
        # Return structured response
        return {
            "status": "success",
            "data": result,
            "message": f"Processed {param} successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "data": None
        }
```

### 3. Workflow Organization
- **Modular Design**: Break complex workflows into reusable components
- **State Management**: Use appropriate memory/state for context
- **Logging**: Implement comprehensive logging
- **Testing**: Test agents individually and in combination

### 4. Performance Optimization
- **Model Selection**: Use appropriate models for tasks
  - `gemini-2.0-flash`: Fast, general tasks
  - `gemini-pro`: Complex reasoning
  - `gemini-ultra`: Most demanding tasks
- **Parallel Processing**: Use Parallel workflows when possible
- **Caching**: Cache expensive operations
- **Batch Processing**: Group similar operations

### 5. Security & Safety
- **Input Validation**: Always validate user inputs
- **Sandboxing**: Use sandboxed environments for code execution
- **Rate Limiting**: Implement rate limits for API calls
- **Sensitive Data**: Never log sensitive information

## Migration Guide

### From Gemini CLI
```python
# Before (Gemini CLI)
# Single monolithic prompt execution

# After (ADK)
from google.adk.agents import LlmAgent

# Break into specialized agents
agent = LlmAgent(
    name="task_agent",
    model="gemini-2.0-flash",
    instruction=refined_prompt,
    tools=structured_tools
)
```

### From LangChain
```python
# LangChain
from langchain.agents import create_react_agent
chain_agent = create_react_agent(llm, tools, prompt)

# ADK equivalent
from google.adk.agents import LlmAgent
from google.adk.tools.langchain_tool import LangchainTool

adk_agent = LlmAgent(
    name="react_agent",
    model="gemini-2.0-flash",
    tools=[LangchainTool(t) for t in tools],
    instruction=prompt.template
)
```

### From CrewAI
```python
# CrewAI
from crewai import Agent, Crew
crew_agent = Agent(role="researcher", goal="find info")

# ADK equivalent
from google.adk.agents import LlmAgent
adk_agent = LlmAgent(
    name="researcher",
    description="find info",
    model="gemini-2.0-flash"
)
```

## Advanced Features

### 1. Streaming Responses
```python
agent = LlmAgent(
    name="streamer",
    model="gemini-2.0-flash",
    streaming=True
)

for chunk in agent.stream("Generate long response"):
    print(chunk, end="")
```

### 2. Function Calling
```python
agent = LlmAgent(
    name="function_caller",
    model="gemini-2.0-flash",
    tools=[calculate, analyze, generate],
    function_calling_mode="auto"  # or "required", "none"
)
```

### 3. Multi-Modal Support
```python
from google.adk.agents import LlmAgent
from google.adk.tools import analyze_image

agent = LlmAgent(
    name="vision_agent",
    model="gemini-2.0-flash",
    tools=[analyze_image],
    instruction="Analyze images and describe what you see"
)

result = agent.run(image_path="photo.jpg")
```

### 4. Evaluation Framework
```python
from google.adk.evaluation import Evaluator

evaluator = Evaluator(
    agent=my_agent,
    test_cases=[
        {"input": "test1", "expected": "result1"},
        {"input": "test2", "expected": "result2"}
    ]
)

results = evaluator.evaluate()
print(f"Accuracy: {results['accuracy']}")
```

### 5. Deployment Options

#### Local Development
```bash
adk web  # Development UI
adk run  # Terminal interface
adk api_server  # REST API
```

#### Vertex AI Agent Engine
```python
from google.adk.deployment import VertexAIDeployment

deployment = VertexAIDeployment(
    agent=my_agent,
    project_id="my-project",
    region="us-central1"
)

deployment.deploy()
```

#### Cloud Run
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install google-adk
CMD ["adk", "api_server", "--port", "8080"]
```

#### Docker
```bash
docker build -t my-agent .
docker run -p 8080:8080 my-agent
```

### 6. Monitoring & Observability
```python
from google.adk.monitoring import Monitor

monitor = Monitor(
    agent=my_agent,
    metrics=["latency", "token_usage", "success_rate"],
    export_to="cloud_monitoring"  # or "prometheus", "local"
)

monitored_agent = monitor.wrap(my_agent)
```

### 7. A/B Testing
```python
from google.adk.experiments import ABTest

test = ABTest(
    agents=[agent_v1, agent_v2],
    traffic_split=[0.5, 0.5],
    metrics=["accuracy", "latency"]
)

test.run(duration_hours=24)
results = test.get_results()
```

## Common Patterns

### 1. Retry with Backoff
```python
from google.adk.patterns import retry_with_backoff

@retry_with_backoff(max_attempts=3, initial_delay=1)
def unreliable_operation():
    # Operation that might fail
    pass
```

### 2. Circuit Breaker
```python
from google.adk.patterns import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60
)

agent = breaker.wrap(unreliable_agent)
```

### 3. Rate Limiting
```python
from google.adk.patterns import RateLimiter

limiter = RateLimiter(
    max_requests=100,
    window_seconds=60
)

limited_agent = limiter.wrap(api_agent)
```

### 4. Caching
```python
from google.adk.patterns import Cache

cache = Cache(
    ttl_seconds=3600,
    max_size=1000
)

cached_agent = cache.wrap(expensive_agent)
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
```python
# Check API key
import os
assert os.getenv('GOOGLE_API_KEY'), "API key not set"
```

2. **Model Not Available**
```python
# Use fallback model
try:
    agent = LlmAgent(model="gemini-ultra")
except ModelNotAvailable:
    agent = LlmAgent(model="gemini-2.0-flash")
```

3. **Rate Limiting**
```python
# Implement exponential backoff
import time
for i in range(3):
    try:
        result = agent.run(input)
        break
    except RateLimitError:
        time.sleep(2 ** i)
```

4. **Memory Issues**
```python
# Clear memory periodically
agent.memory.clear()
# Or limit memory size
agent.memory = ConversationMemory(max_turns=5)
```

## Resources

### Official Resources
- **Documentation**: https://google.github.io/adk-docs/
- **GitHub**: https://github.com/google/adk-python
- **Examples**: https://github.com/google/adk-python/tree/main/examples
- **API Reference**: https://google.github.io/adk-docs/api/

### Community
- **Reddit**: r/agentdevelopmentkit
- **Discord**: ADK Community Server
- **Stack Overflow**: [google-adk] tag

### Related Projects
- **Gemini API**: https://ai.google.dev/
- **Vertex AI**: https://cloud.google.com/vertex-ai
- **LangChain**: https://langchain.com/
- **CrewAI**: https://crewai.com/

### Tutorials & Guides
1. Building Your First Agent
2. Multi-Agent Collaboration
3. Production Deployment
4. Performance Optimization
5. Security Best Practices

## Version History

- **v1.0.0** (Jan 2025): Initial release at Cloud NEXT
- **v1.1.0**: Added MCP support
- **v1.2.0**: Enhanced workflow patterns
- **v1.3.0**: Vertex AI Agent Engine integration

## License

Apache 2.0 License

---
Document Version: 1.0
Last Updated: 2025-01-11
Comprehensive guide for ADK development and migration