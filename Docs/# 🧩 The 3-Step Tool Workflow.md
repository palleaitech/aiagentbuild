# 🧩 The 3-Step Tool Workflow

To make an agent use tools, LangChain follows a simple three-step pipeline:

## 1. Tool Declaration

Create standard Python functions and decorate them with `@tool` to convert them into LangChain tools.

* Define a clear function name.
* Add type hints for all parameters.
* Write descriptive docstrings because the LLM uses them to understand when and how to use the tool.

## 2. Tool Binding

Bind the tools to your LLM so the model is aware of:

* The available tools
* Their purpose
* Required inputs
* Expected outputs

Once bound, the model can decide when a tool is needed during a conversation.

## 3. Execution Loop

When a user submits a prompt:

1. The LLM analyzes the request.
2. It determines whether a tool is required.
3. It generates a structured tool call.
4. The tool executes.
5. The result is returned to the LLM.
6. The LLM uses the result to formulate the final response.

***

# 💻 Fast-Track Example: Your First Multi-Tool Agent

The following script demonstrates the complete workflow of defining tools, binding them to an LLM, and running an agent capable of automatically selecting and invoking the appropriate tool.

```python
import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


# 1. Declare tools with clear descriptions
# The LLM reads these docstrings when determining tool usage.

@tool
def calculate_prime_factors(number: int) -> str:
    """Calculates the prime factors of a given integer. Use this for complex math."""
    
    # Dummy logic for demonstration
    if number == 84:
        return "2 * 2 * 3 * 7"
    
    return "Calculated factors successfully."


@tool
def get_system_status(service_name: str) -> str:
    """Checks the live operational status of a specific internal database or service."""
    
    return f"The service '{service_name}' is fully operational and healthy."


# 2. Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

# 3. Create an agent with the bound tools
tools = [calculate_prime_factors, get_system_status]
agent = create_react_agent(llm, tools)

# 4. Test the agent
query = (
    "Check if the 'payment_gateway' is working, "
    "and then find the prime factors of 84."
)

response = agent.invoke(
    {
        "messages": [
            ("human", query)
        ]
    }
)

# Print the final agent response
print(response["messages"][-1].content)
```

***

# ⚙️ What Happens Internally?

Given the user request:

```text
Check if the 'payment_gateway' is working, and then find the prime factors of 84.
```

The agent will:

1. Call `get_system_status("payment_gateway")`
2. Receive the service status
3. Call `calculate_prime_factors(84)`
4. Receive the factorization result
5. Generate a combined natural-language response

This entire process happens automatically without manually invoking either function.

***

# 💡 Golden Rules for Building Tools

## 1. Docstrings Are Instructions

The content inside triple quotes (`""" ... """`) is not just developer documentation.

LangChain sends these descriptions to the LLM so it can decide:

* When to use the tool
* Why to use the tool
* What type of task the tool solves

### Poor Example

```python
@tool
def calculate(number: int):
    """Does math."""
```

### Better Example

```python
@tool
def calculate_prime_factors(number: int):
    """Calculates the prime factors of a given integer. Use this for complex math problems involving factorization."""
```

The more specific the description, the more reliably the agent will use the tool.

***

## 2. Type Hints Matter

Always use explicit Python type hints.

```python
def calculate_prime_factors(number: int) -> str:
```

LangChain automatically converts type hints into JSON schemas, allowing the model to understand:

* Required fields
* Expected data types
* Valid tool inputs

### Good Examples

```python
name: str
age: int
price: float
is_active: bool
```

### Avoid

```python
def process(data):
```

Without type hints, the model has less information about the expected input structure.

***

# ✅ Key Takeaways

* Use `@tool` to convert Python functions into agent tools.
* Write clear and descriptive docstrings.
* Use explicit Python type hints.
* Bind tools to the LLM before running the agent.
* The agent automatically decides when to call tools.
* Tool outputs are fed back into the LLM to generate the final response.
* Well-defined tools significantly improve agent reliability and accuracy.
## //------------------------------------------------------------------------------------------//
````md
# How LangChain Uses Docstrings as LLM Prompts

In LangChain, the text inside a tool's triple-quoted docstring (`""" ... """`) serves directly as part of the prompt provided to the Large Language Model (LLM).

When you apply the `@tool` decorator, LangChain automatically extracts the function's docstring and includes it in the tool definition that is sent to the model. This description helps the LLM understand **what the tool does**, **when it should be used**, and **what inputs it requires**.

## How the LLM Interprets a Tool

Consider the following example:

```python
from langchain.tools import tool

@tool
def check_inventory(item_name: str) -> str:
    """Check the real-time stock levels of a specific item in our warehouse."""
    return f"{item_name} is in stock."
````

### What Happens Behind the Scenes?

LangChain converts the Python function into a structured schema that the LLM can understand. The function name, docstring, type hints, and parameters are transformed into a tool specification similar to the following:

```json
{
  "name": "check_inventory",
  "description": "Check the real-time stock levels of a specific item in our warehouse.",
  "parameters": {
    "type": "object",
    "properties": {
      "item_name": {
        "type": "string"
      }
    },
    "required": ["item_name"]
  }
}
```

## Mapping Python Code to Tool Schema

| Python Component  | Tool Schema Representation |
| ----------------- | -------------------------- |
| `check_inventory` | `name`                     |
| Docstring         | `description`              |
| `item_name: str`  | Parameter definition       |
| Type hints        | JSON parameter types       |
| Return type       | Tool output expectation    |

## Why the Docstring Matters

The docstring is one of the most important parts of a LangChain tool because it tells the LLM:

* What the tool does
* When it should be used
* What information it returns
* How it differs from other available tools

For best results, write clear, specific, and action-oriented docstrings. A well-written description significantly improves the model's tool-selection accuracy.

## Summary

When using the `@tool` decorator, LangChain automatically converts your Python function into a machine-readable tool schema. The function's docstring becomes the tool description that is injected into the instructions available to the LLM, enabling the model to understand and correctly invoke the tool when appropriate.

```
```

## /-----------------------------------------------------------------------------------------/
The LangGraph Agent LoopEvery time your user sends a message, LangGraph spins up a loop that looks exactly like this diagram:

graph TD
    Start([User Input]) --> State[1. Shared State: Memory & Conversation History]
    State --> Agent[2. Agent Node: LLM processes input & selects tool]
    Agent --> Decision{3. Conditional Edge: Needs a tool?}
    
    Decision -- YES --> ToolNode[4. Action Node: Executes Python function]
    ToolNode --> State
    
    Decision -- NO --> End([Final Response Sent to User])

    style Start fill:#f9f,stroke:#333,stroke-width:2px
    style End fill:#bbf,stroke:#333,stroke-width:2px
    style Decision fill:#f96,stroke:#333,stroke-width:2px
    style ToolNode fill:#8f8,stroke:#333,stroke-width:2px
    style Agent fill:#8bf,stroke:#333,stroke-width:2px

## 🧩 The 4 Parts of the Loop Explained

### 1. Shared State — *The Brain's Notebook*

The **Shared State** is a Python dictionary (or similar object) that stores the conversation's current context, including messages, tool outputs, and other relevant data.

* Every node can **read from it**.
* Nodes can **add new information** to it.
* The updated state is then **passed to the next step** in the workflow.

Think of it as the agent's **short-term memory**, ensuring every component works from the same source of truth.

***

### 2. Agent Node — *The Thinker*

The **Agent Node** contains the LLM.

Its role is to:

* Review the current **State**.
* Understand the user's request.
* Decide what action to take next.

The LLM can either:

* Generate a final answer directly, or
* Determine that it needs assistance from a tool to complete the task.

***

### 3. Conditional Edge — *The Decision Maker*

The **Conditional Edge** controls the routing logic of the graph.

It works like an **if/else statement**:

* If the LLM produces a normal text response, the workflow routes to **END**.
* If the LLM produces a tool-call request (for example, a JSON structure requesting `calculate_prime_factors`), the workflow routes to the **Action Node**.

This component decides the next path based on the agent's output.

***

### 4. Action Node — *The Doer*

The **Action Node** executes the actual tool or function.

Its responsibilities are to:

1. Receive the tool name and arguments from the LLM.
2. Run the corresponding Python function.
3. Add the tool's result back into the **State**.
4. Send the updated State back to the **Agent Node**.

This creates a feedback loop where the LLM can use the newly generated information to continue reasoning and produce a final response.

***

### 🔄 How the Loop Works Together

```text
Shared State
      ↓
 Agent Node (Thinker)
      ↓
Conditional Edge (Decision Maker)
      ↓
 ┌───────────────┐
 │ Tool Needed?  │
 └───────┬───────┘
         │ Yes
         ↓
 Action Node (Doer)
         ↓
   Update State
         ↓
 Agent Node
         ↓
      END
     (when no tool is needed)
```

Together, these four components create a continuous **Think → Decide → Act → Update → Think** cycle that powers tool-using AI agents.
