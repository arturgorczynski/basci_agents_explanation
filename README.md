# Multi-Agent AI System

A sophisticated multi-agent AI system that orchestrates specialized AI agents to solve complex tasks through collaborative problem-solving.

## 🎯 System Overview

This system implements a **collaborative AI workforce** where each agent specializes in different aspects of problem-solving, working together under the guidance of a central manager to complete complex tasks that require multiple skills and tools.

## 🤖 Agent Architecture

### **Manager (CommandCentre)**
- **Role**: The "brain" of the operation - orchestrates the entire process
- **Capabilities**: Planning, delegation, task synthesis, and final answer generation
- **Tools**: Brain tools, common tools
- **Personality**: Strategic planner and coordinator

### **Python Developer**
- **Role**: Code specialist for data analysis and automation
- **Capabilities**: Writing Python code, executing scripts, data analysis
- **Tools**: Programmer tools, common tools
- **Personality**: Meticulous developer with attention to detail

### **Secretary**
- **Role**: File management and data handling specialist
- **Capabilities**: Reading/writing files, CSV/JSON processing, file searching
- **Tools**: File handler tools, common tools
- **Personality**: Expert in file management and organization

### **Intern**
- **Role**: General purpose agent for miscellaneous tasks
- **Capabilities**: Utility functions, user communication, general assistance
- **Tools**: Utils handler, common tools
- **Personality**: Versatile helper for various tasks

### **API Communicator**
- **Role**: External data retrieval specialist
- **Capabilities**: Weather data, geolocation, external API integration
- **Tools**: APIs tools
- **Personality**: API specialist with cautious parameter handling

## 🔄 Execution Flow

1. **User Request**: System receives a user query
2. **Manager Planning**: Manager analyzes the request and plans the next step
3. **Agent Selection**: Manager delegates to the most suitable agent
4. **Tool Execution**: Agent chooses and executes the appropriate tool
5. **Result Processing**: Results are stored and the cycle repeats
6. **Final Synthesis**: Manager synthesizes all data for the final answer

## 🛠️ Tool Categories

### **Brain Tools**
- Final synthesis and task completion
- Triggers the manager's comprehensive answer generation

### **File Handler Tools**
- File operations (read/write/search)
- CSV and JSON processing
- Directory management

### **Programmer Tools**
- Python code writing and execution
- Script generation and running

### **API Tools**
- Weather forecasts and geolocation
- External data retrieval

### **Common Tools**
- User communication and feedback

### **Utils Tools**
- General utilities and helper functions

## 📊 Memory Management

The system uses three types of memory:

1. **Structured Memory**: Tracks execution steps and agent actions
2. **Unstructured Memory**: Stores general information and user requests
3. **Token Usage Memory**: Monitors API costs and usage

## 🎨 Key Features

- **Modular Design**: Each agent has specific responsibilities
- **Memory Persistence**: Tracks execution across sessions
- **Error Handling**: Adapts strategies when steps fail
- **Cost Tracking**: Monitors API token usage
- **Extensible**: Easy to add new agents or tools
- **Visual Feedback**: Clear logging with emojis and colors

## 🚀 Usage Examples

The system can handle various complex tasks:

1. **Weather-based clothing recommendations** using wardrobe data and weather APIs
2. **Distance calculations** between locations using geolocation
3. **Data analysis** with automated plotting and visualization
4. **File processing** and data manipulation

## 📁 Project Structure

```
multi_ai_agent_updated/
├── agents_training_facility/    # Agent definitions and personalities
├── tools/                       # Tool implementations for each agent
├── memory/                      # Memory management system
├── prompts/                     # System prompts for agent communication
├── toolbox/                     # Tool management and execution
├── data/                        # Sample data files
└── main.py                      # Main execution orchestrator
```

## 🔧 Getting Started

### Environment variables

Create a `.env` file in the project root with:

```env
MODEL_PROVIDER=azure
POSITIONSTACK_API_KEY=your_positionstack_api_key
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=gpt-4o-ArturG
```

Important notes:
- The code now supports both Azure OpenAI and Ollama.
- Set `MODEL_PROVIDER=azure` to use Azure OpenAI.
- Set `MODEL_PROVIDER=ollama` to use Ollama.
- `POSITIONSTACK_API_KEY` is required only for address-to-geolocation features.
- Open-Meteo does not need an API key.

Example Ollama configuration:

```env
MODEL_PROVIDER=ollama
POSITIONSTACK_API_KEY=your_positionstack_api_key
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma3:27b
OLLAMA_API_KEY=ollama
```

### Install dependencies

There is no dependency lockfile in this repository, so install the packages manually:

```bash
pip install openai python-dotenv requests pandas termcolor
```

### Run the app

1. Create and activate a virtual environment.
2. Install the dependencies.
3. Create `.env` from `.env.example`.
4. Run:

```bash
python main.py
```

5. Enter a request in the terminal and let the agents execute step by step.

### Example prompts

- `Check weather near Wawozowa 32b/1 Krakow and my_wardrobe.json file that have info about my wardrobe and provide me with info what shall I wear today. Please note that I rather be cold than to hot.`
- `I am sitting in Wawozowa 32, Krakow, Poland while my wife is at Grunwaldzka 12, Nowy Sacz, Poland -- what is distance between us right now?`
- `there is housing.csv file -- please save two plots that will show relation between all or given featurds on price?`

## 💡 Optimization Features

- **Repetition Prevention**: Memory tracking prevents redundant operations
- **Error Recovery**: System adapts when tools fail
- **Cost Optimization**: Token usage monitoring
- **Visual Feedback**: Clear status updates throughout execution
- **Memory Persistence**: Maintains context across sessions 
