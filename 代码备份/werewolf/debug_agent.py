
import json
import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional

from jinja2 import Template

from openagents.models.event_context import EventContext
from openagents.models.tool import AgentTool
from openagents.models.agent_config import AgentConfig
from openagents.models.agent_actions import (
    AgentTrajectory,
    AgentAction,
    AgentActionType,
)
from openagents.config.llm_configs import (
    determine_provider,
    create_model_provider,
    is_auto_model,
    resolve_auto_model_config,
)
from openagents.utils.verbose import verbose_print
from openagents.agents.collaborator_agent import CollaboratorAgent

print("\n" + "█" * 40)
print(">>> DEBUG AGENT MODULE LOADED <<<")
print("█" * 40 + "\n")

logger = logging.getLogger(__name__)

def _create_finish_tool() -> AgentTool:
    """Create a tool that allows the model to indicate it's finished with actions."""
    return AgentTool(
        name="finish",
        description="Use this tool when you have completed all necessary actions and don't need to do anything else.",
        input_schema={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for finishing the action chain.",
                }
            },
            "required": ["reason"],
        },
        func=lambda reason: f"Action chain completed: {reason}",
    )

async def debug_orchestrate_agent(
    context: EventContext,
    agent_config: AgentConfig,
    tools: List[AgentTool],
    user_instruction: Optional[str] = None,
    max_iterations: Optional[int] = None,
    disable_finish_tool: Optional[bool] = False,
    use_llm_user_prompt: Optional[bool] = False,
    agent_id: Optional[str] = None,
    agent_client = None,
) -> AgentTrajectory:
    """
    Custom orchestration function with debug printing for LLM prompts and timing.
    """
    if max_iterations is None:
        if agent_config.max_iterations is None:
            max_iterations = 10
        else:
            max_iterations = agent_config.max_iterations

    actions = []
    incoming_message = context.incoming_event
    incoming_thread_id = context.incoming_thread_id
    event_threads = context.event_threads
    
    # Initialize logger logic skipped for simplicity as we want direct print debugging

    # Resolve model provider
    if is_auto_model(agent_config.model_name):
        auto_config = resolve_auto_model_config()
        model_name = auto_config.get("model_name")
        provider_name = auto_config.get("provider")
        api_key = auto_config.get("api_key")
        base_url = auto_config.get("base_url")

        if not model_name:
            raise ValueError("Model 'auto' resolving failed.")

        effective_base_url = base_url or agent_config.api_base

        provider = determine_provider(provider_name, model_name, effective_base_url)
        model_provider = create_model_provider(
            provider=provider,
            model_name=model_name,
            api_base=effective_base_url,
            api_key=api_key or agent_config.api_key,
        )
    else:
        provider = determine_provider(
            agent_config.provider, agent_config.model_name, agent_config.api_base
        )
        model_provider = create_model_provider(
            provider=provider,
            model_name=agent_config.model_name,
            api_base=agent_config.api_base,
            api_key=agent_config.api_key,
        )

    # Template rendering
    template_context = type(
        "TemplateContext",
        (),
        {
            "event_threads": event_threads,
            "incoming_thread_id": incoming_thread_id,
            "incoming_event": incoming_message,
        },
    )()

    if use_llm_user_prompt:
        user_template = Template(agent_config.llm_user_prompt_template)
    else:
        user_template = Template(agent_config.user_prompt_template)
    
    prompt_content = user_template.render(
        context=template_context, user_instruction=user_instruction
    ).strip()

    system_content = (
        Template(agent_config.get_effective_system_prompt_template())
        .render(instruction=agent_config.instruction)
        .strip()
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt_content},
    ]

    all_tools = list(tools)
    if not disable_finish_tool:
        finish_tool = _create_finish_tool()
        all_tools.append(finish_tool)

    formatted_tools = model_provider.format_tools(all_tools)

    is_finished = False
    iteration = 0

    while not is_finished and iteration < max_iterations:
        iteration += 1

        try:
            call_start_time = time.time()
            
            # --- CUSTOM DEBUG PRINT ---
            print("\n" + "█" * 60)
            print(f"🤖 [DebugAgent] LLM REQUEST | Time: {datetime.now().strftime('%H:%M:%S')}")
            print(f"📍 Agent: {agent_id or 'Unknown'}")
            print(f"🔧 Tools: {[t.name for t in all_tools]}")
            print("-" * 60)
            print("📝 PROMPT (Last Message):")
            print(json.dumps(messages[-1], indent=2, ensure_ascii=False))
            print("█" * 60 + "\n")
            # --------------------------

            response = await model_provider.chat_completion(messages, formatted_tools)
            
            call_end_time = time.time()
            latency = call_end_time - call_start_time
            print(f"✅ [DebugAgent] LLM RESPONSE | Latency: {latency:.2f}s")

            # Basic response handling loop (simplified for debug purpose)
            assistant_message = {"role": "assistant"}
            
            if response.get("tool_calls"):
                formatted_tool_calls = []
                for tool_call in response["tool_calls"]:
                    formatted_tool_calls.append({
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": tool_call["arguments"],
                        },
                    })
                assistant_message["tool_calls"] = formatted_tool_calls
                assistant_message["content"] = response.get("content") or ""
            else:
                assistant_content = response.get("content") or ""
                assistant_message["content"] = assistant_content
                if not assistant_content:
                    is_finished = True # Bail out
            
            messages.append(assistant_message)

            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["name"]
                    
                    # Tool Execution Action
                    action = AgentAction(
                        action_id=str(uuid.uuid4()),
                        action_type=AgentActionType.CALL_TOOL,
                        timestamp=datetime.now(),
                        payload={
                            "tool_name": tool_name,
                            "arguments": tool_call["arguments"],
                        },
                    )
                    actions.append(action)

                    if tool_name == "finish":
                        is_finished = True
                        # Assume success finish
                        break
                    
                    # Execute
                    tool = next((t for t in tools if t.name == tool_name), None)
                    result_str = "Tool not found"
                    if tool:
                        try:
                            args = json.loads(tool_call["arguments"])
                            result = await tool.execute(**args)
                            result_str = str(result)
                        except Exception as e:
                            result_str = f"Error: {e}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result_str,
                    })

            else:
                # Direct response
                is_finished = True
                actions.append(AgentAction(
                    action_id=str(uuid.uuid4()),
                    action_type=AgentActionType.COMPLETE,
                    timestamp=datetime.now(),
                    payload={"response": response.get("content")},
                ))

        except Exception as e:
            print(f"❌ [DebugAgent] Error: {e}")
            break
            
    summary = "Debug Agent completed interaction."
    return AgentTrajectory(actions=actions, summary=summary)


class WerewolfDebugAgent(CollaboratorAgent):
    """
    A custom agent for Werewolf that uses the debug orchestrator
    to print LLM prompts and timing information.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print(f">>> 🐛 DEBUG AGENT INIT: {self.agent_id}")
    
    async def run_agent(
        self,
        context: EventContext,
        instruction: Optional[str] = None,
        max_iterations: Optional[int] = None,
        disable_mcp: Optional[bool] = False,
        disable_mods: Optional[bool] = False,
    ) -> AgentTrajectory:
        """
        Override to use debug_orchestrate_agent
        """
        tools = []
        if not disable_mcp:
            tools.extend(self._mcp_tools)
        if not disable_mods:
            tools.extend(self._mod_tools)
        tools.extend(self._custom_tools)
        
        return await debug_orchestrate_agent(
            context=context,
            agent_config=self.agent_config,
            tools=tools,
            user_instruction=instruction,
            max_iterations=max_iterations,
            agent_id=self.agent_id,
            agent_client=self._network_client,
        )

    async def react(self, context: EventContext):
        """
        Override react to properly handle react_to_direct_messages which is missing in base class.
        """
        # 1. Check Triggers
        trigger = self._triggers_map.get(context.incoming_event.event_name)
        if trigger:
            logger.debug(f"Trigger found for event: {context.incoming_event.event_name}")
            await self.run_agent(context=context, instruction=trigger.instruction)
            return

        # 2. Check Direct Messages
        is_dm = context.incoming_event.destination_id == self.agent_id
        if is_dm and self.agent_config and self.agent_config.react_to_direct_messages:
            logger.debug(f"Handling Direct Message (react_to_direct_messages=True)")
            await self.run_agent(context=context)
            return

        # 3. Check All Messages
        if self.agent_config and self.agent_config.react_to_all_messages:
            logger.debug(f"Handling Message (react_to_all_messages=True)")
            await self.run_agent(context=context)
            return
            
        logger.debug(f"Ignored event: {context.incoming_event.event_name}")
