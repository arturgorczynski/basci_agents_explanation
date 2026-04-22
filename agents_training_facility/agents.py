from termcolor import colored
import os
import inspect
import json
from typing import List
from memory.memory_manager import Memory
from datetime import datetime

current_time = datetime.now()
formatted_time = current_time.strftime('%d-%m-%Y %H:%M')

from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI

#from collections import deque
#from tools.file_handler import text_writer, text_reader, csv_reader
#from tools.utils_handler import reverse_string, talk, check_or_create_path, write_python_code, run_python_script

from prompts.prompts import agent_choose_tool_system 
from toolbox.toolbox import ToolBox
from tools import brain, common, file_handler, programer, utils_handler, apis

load_dotenv()

available_tools = {
    'brain': brain,
    'apis': apis,
    'common': common,
    'file_handler': file_handler,
    'programer': programer,
    'utils_handler': utils_handler,

}

class Agent:
    # Class-level dictionary to store agents and their missions
    agent_registry = {}
    
    token_usage = Memory(is_structured=False)

    def __init__(self, name, module_list: List[str], agent_mission: str, agent_personality: str ):
        """
        Initializes the agent with a list of tools and a mission.

        Parameters:
        tools (list): List of tool functions available for agent to use.
        agent_mission (str): The mission assigned to the agent.
        """
        self.name = name
        self.module_list = module_list  # Store the tool names
        self.toolbox = ToolBox() 
        self.available_functions = []
        self.active_abilities =  self.get_function_dict()
        self.agent_personality = agent_personality

        self.field_agent = True
        self.agent_mission = agent_mission
        self.model_provider, self.model = self._load_model_settings()

        # Retrieve the variable name of the instance
        self.client = self._gpt_client()

        ## dynamically build toolset for an agent
        selected_functions = []
        for tool_name in module_list:
            if tool_name in available_tools:
                # Add all callable functions from the tool module
                module = available_tools[tool_name]
                module_functions = [func for func in vars(module).values() if callable(func)]
                selected_functions += module_functions
                
                # Store only the function names in available_functions
                self.available_functions += [func.__name__ for func in module_functions]
        
        # Store the selected functions in the toolbox
        self.toolbox.store(selected_functions)
        
        # Add the agent and its mission to the registry
        Agent.agent_registry[self.name] = {'mission':self.agent_mission, 'tools to use': (', ').join(self.available_functions), 'field_agent':self.field_agent}  # Fixed the incorrect attribute name

    def _get_required_env(self, env_name):
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        raise ValueError(f"Missing required environment variable: {env_name}")

    def _load_model_settings(self):
        provider = os.getenv("MODEL_PROVIDER", "azure").strip().lower()
        if provider not in {"azure", "ollama"}:
            raise ValueError("MODEL_PROVIDER must be either 'azure' or 'ollama'.")

        if provider == "azure":
            model_name = self._get_required_env("AZURE_OPENAI_DEPLOYMENT")
        else:
            model_name = self._get_required_env("OLLAMA_MODEL")

        return provider, model_name

    def _gpt_client(self):
        if self.model_provider == "azure":
            api_key = self._get_required_env("AZURE_OPENAI_API_KEY")
            azure_endpoint = self._get_required_env("AZURE_OPENAI_ENDPOINT")
            api_version = self._get_required_env("AZURE_OPENAI_API_VERSION")

            return AzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
            )

        ollama_base_url = self._get_required_env("OLLAMA_BASE_URL")
        ollama_api_key = self._get_required_env("OLLAMA_API_KEY")

        return OpenAI(
            base_url=ollama_base_url,
            api_key=ollama_api_key,
        )

    def _parse_json_response(self, model_content):
        cleaned_content = model_content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content.strip("`")
            if cleaned_content.startswith("json"):
                cleaned_content = cleaned_content[4:]
            cleaned_content = cleaned_content.strip()
        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            json_start = cleaned_content.find("{")
            json_end = cleaned_content.rfind("}")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                return json.loads(cleaned_content[json_start:json_end + 1])
            raise
    
    
    def _ask_agent(self, system_prompt, prompt='', return_json=False):
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}]
        # Modify request based on whether JSON output is requested
        request_params = {
            "model": self.model,
            "messages": messages}

        if return_json:
            if self.model_provider == "azure":
                request_params['response_format']= {"type":'json_object'}
            else:
                messages[0]["content"] += "\nReturn only a valid JSON object with no markdown fences."

        response = self.client.chat.completions.create(**request_params)

        if return_json:
            model_response = self._parse_json_response(response.choices[0].message.content)
        else: 
            model_response = response.choices[0].message.content

        # Extract token usage from the response
        usage = getattr(response, "usage", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        
        # Save info about usage as list = time, request, output_tokens, input_tokens
        model_data = [formatted_time, model_response, completion_tokens, prompt_tokens]


        self.token_usage.extend_memory([model_data])
        
        self.token_usage.save_history("memory/execution_cost/token_usage.txt")
        return model_response
   
    def get_function_dict(self):
        modules = self.module_list

        function_to_module_mapping = {}

        # Loop through each module
        for module_name in modules:
            module = globals()[module_name]
            functions = inspect.getmembers(module, inspect.isfunction)
            
            for func_name, func_obj in functions:
                function_to_module_mapping[func_name] = module

        return function_to_module_mapping  


    def think(self, prompt):
        """
        Runs the generate_text method on the model using the system prompt template and tool descriptions.

        Parameters:
        prompt (str): The user query to generate a response for.

        Returns:
        dict: The response from the model as a dictionary.
        """

        tool_descriptions = self.toolbox.tools()
        agent_system_prompt = agent_choose_tool_system.format(agent_descriptions= self.agent_personality, tool_descriptions=tool_descriptions)

        agent_response_dict = self._ask_agent(agent_system_prompt, prompt, return_json=True)

        return agent_response_dict
    
    def execute_tool(self, agent_response_dict):
        """
        Executes the tool chosen by the agent with the provided input.

        Parameters:
        agent_response_dict (dict): A dictionary containing 'tool_choice' and 'tool_input'.
        """
        tool_choice = agent_response_dict.get("tool_choice")
        tool_input = agent_response_dict.get("tool_input")

        tool_found = False
        for tool in self.toolbox.tools_dict:
            if tool == tool_choice:
                print(colored(f"| Tool Choice Step | Tool {tool_choice} : Arguments {tool_input}", 'light_magenta'))
                tool_found = True
                tool_func = getattr(self.active_abilities[tool_choice], tool_choice)
                if isinstance(tool_input, dict):
                    response = tool_func(**tool_input)
                else:
                    response = tool_func(tool_input)
                return response

        if not tool_found:
            print(f"Tool {tool_choice} not found in agent's toolbox.")
        return None


class CommandCentre(Agent):

    def __init__(self, name, tools: list, agent_mission: str, agent_personality:str):
        """
        Initializes the CommandCentre with a list of tools and a mission, 
        but does not add it to the agent registry.

        Parameters:
        tools (list): List of tool functions.
        agent_mission (str): The mission assigned to the CommandCentre.
        """
        # Initialize the parent Agent class without adding to registry
        super().__init__(name, tools, agent_mission, agent_personality)
        
        # Remove the entry from the agent registry if it exists
        # if self.name in Agent.agent_registry:
        #    del Agent.agent_registry[self.name]

    def _get_agents_characteristics(self):
        agents_list = """"""
        for k,v in self.agent_registry.items():
                agents_list += f"Agent name -- {k} -- Agent {k} || Mission {v['mission']} || Tools to used: {v['tools to use']} \n"
        
        return agents_list

    
    #def decide_if_task_done
