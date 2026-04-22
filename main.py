# https://dslackw.gitlab.io/colored/tables/colors/

from agents_training_facility import agents, personalities
from dotenv import load_dotenv
import os
import json
import sys
from termcolor import colored
from prompts.prompts import  plan_next_step_system, plan_next_step_user, agent_choose_tool_user, synthesis_system, synthesis_user
import traceback
from memory.memory_manager import Memory
import time

try:
    import pandas as pd
except ImportError:
    pd = None

load_dotenv()

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

STEPS_TO_TRACK = 10

### Utils
#-----------------------------------------------------------------------------------
def get_key( diction):
    return list(diction.keys())[0]
def get_value( diction):
    return list(diction.values())[0]


def summarize_tool_result(result):
    if pd is not None and isinstance(result, pd.DataFrame):
        preview = result.head(5).to_string(index=False)
        return f"DataFrame shape={result.shape}\n{preview}"
    return result




### Agents setup and definition 
#-----------------------------------------------------------------------------------
long_history = Memory(is_structured=False)
step_history = Memory(is_structured=True)
requests_history = Memory(is_structured=False)


manager = agents.CommandCentre('manager', ['brain', 'common'],personalities.brain_desc, personalities.brain_system)
python_developer = agents.Agent('pythondeveloper', ['programer', 'common'],personalities.python_developer_desc, personalities.python_developer_system)
secretary = agents.Agent('secretary', ['file_handler', 'common'],personalities.secretary_desc, personalities.secretary_system)
intern = agents.Agent('intern', ['utils_handler', 'common'],personalities.intern_desc, personalities.intern_system)
api = agents.Agent('api', ['apis'],personalities.communicator_desc, personalities.communicator_system)


agents_dict = {manager.name:manager,
               python_developer.name:python_developer,
               secretary.name:secretary,
               intern.name:intern,
               api.name:api}

agents_list = manager._get_agents_characteristics()


#--------------------------------------------------------------------------------
#  Execution Start
#--------------------------------------------------------------------------------

# Get inital user request
user_request = input("Hello user, I am hear to assist. Please tell how can I help you?: ")
requests_history.extend_memory(user_request)
print(colored(f"| User requested |: {user_request}", "light_blue"))

### Remove information from previosu run to ensure new operation memeory 
if os.path.exists('memory.txt'):
    os.remove('memory.txt')


### Limit max number of iteration to avoid infinite looping
count = 0
while True:
    count += 1
    if count > 9:
        break


    ### Get info about what was done so far and use it in planning next step of execution
    print(f"Step {count}")
    last_actions = step_history.recall_last_actions(STEPS_TO_TRACK)
    formatted_plan_next_step = plan_next_step_user.format(original_request=user_request, steps_executed=last_actions, avaliable_agents=agents_list)
    next_step = manager._ask_agent(plan_next_step_system, formatted_plan_next_step, True)
    print(next_step)
    step_history.extend_memory(next_step)


    if next_step == {'END': 'END'}:
        user_request = input("Your request has been finished. Shall I help with anything else?: ")
        if user_request in ['q', 'quit', 'exit', 'no', 'thanks']:
            break
        print(colored(f"| New user requested |: {user_request}", "light_blue"))
        requests_history.extend_memory(user_request)
        next_step = manager._ask_agent(plan_next_step_system, formatted_plan_next_step, True)
        step_history.extend_memory(next_step)

    '''
    elif next_step == {'END': 'NO RESOURCES TO SOLVE PROBLEM'}:
        user_request = input("Seems like I am missing information or tool to solve request -- please provide missing information: ")
        print(colored(f"| New user requested |: {user_request}", "light_blue"))
        requests_history.extend_memory(user_request)
        continue
    '''

    print(colored(f"| Planning Result | Next Step: {next_step}", "green"))

 

    if get_key(next_step) not in agents_dict.keys():
        print(f'Agent  {get_key(next_step)} not recognized -- routing back to manager')
        step_history.extend_memory({'Last planing step failed due to incorrect agent choice' : 'Please repeat planning step.'})
        continue


    active_agent = agents_dict[get_key(next_step)]
    agent_instruction = get_value(next_step)

    formatted_agent_choose_tool_user = agent_choose_tool_user.format(manager_instruction=agent_instruction, execution_step_history=step_history.recall_last_actions(12), original_request=user_request)
    agent_response_dict = active_agent.think(formatted_agent_choose_tool_user)
    step_history.extend_memory({f"Agent {get_key(next_step)}" : f" used tool {agent_response_dict['tool_choice']} used along with {agent_response_dict['tool_input']} arguments"})

    agent_execution_result = active_agent.execute_tool(agent_response_dict)
    summarized_result = summarize_tool_result(agent_execution_result)
    step_history.extend_memory({'Actions result': summarized_result})

    try:
        if isinstance(agent_execution_result, str) and agent_execution_result == 'FINAL STEP':
            synthesis_user_formatted = synthesis_user.format(original_request=user_request, steps_executed=last_actions)
            answer_to_request = manager._ask_agent(synthesis_system, synthesis_user_formatted)
            print(answer_to_request)
            step_history.extend_memory({'Answer to user question': answer_to_request})
    except Exception as e:
        print(f"Exception occurred: {e}")
        traceback.print_exc() 


    # Save updated execution history
    with open('memory.txt', 'w', encoding='utf-8') as thefile: 
        text = step_history.recall_last_actions(STEPS_TO_TRACK)
        if isinstance(text, list): 
            text = '\n'.join(map(str, text))
        thefile.write(text)


    print(colored(f"| Step Execution | {summarized_result} ", "magenta"))
    print(" ")
    print(" ")
    time.sleep(2)


'Given my_wardrobe.json file that have info about my wardrobe and weather info provide me with info what shall I wear today. Please note that I rather be cold than to hot.'
'Check  weather near Wawozowa 32b/1 Krakow  and my_wardrobe.json file that have info about my wardrobe and provide me with info what shall I wear today. Please note that I rather be cold than to hot.'

'I am sitting in Wawozowa 32, Krakow, Poland while my wife is at Grunwaldzka 12, Nowy Sacz, Poland -- what is distance between us right now?'
'there is housing.csv file -- please save two plots that will show relation between all or given featurds on price? '
