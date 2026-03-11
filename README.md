# Order Fulfillment AI Assistant

This web application provides an intelligent dashboard and an AI-powered chat interface for analyzing and simulating inventory fulfillment under operational constraints.

The project connects to Anthropic's Claude API to translate natural language into analytical queries, computes order fulfillment possibilities using custom constraint algorithms over provided warehouse data, and produces clear, actionable textual summaries for users along with impact metrics.

## File Structure

The backend application has modular components to cleanly separate concerns:

- `app_v3.py`: The main Flask server application. Handles defining the API endpoints (`/`, `/api/chat`, `/api/scenario`) and serving the frontend dashboard application.
- `data.py`: Stores static mock data used by the system, including default inventory tables, part types, and warehouse definitions.
- `orders.py`: Contains data-parsing logic. It loads raw structured log strings line-by-line, parses dates safely, and deduplicates the order datasets for analysis.
- `algorithm.py`: The core constraint engine logic. Simulates sequentially deducting from inventory maps iteratively over active orders. Also includes scenario analysis logic to compute the net-impact of manual inventory adjustments before they occur in the real world, which helps in simulating inventory changes.
- `llm.py`: A wrapper module connecting the application to Anthropic's Claude framework. It defines internal system prompts required for Natural Language Understanding (NLU) to pull constraints out of chat prompts, and builds natural-language summaries based on the algorithm outputs.

- `templates/index.html`: The HTML frontend containing CSS and Javascript logic. Provides the interactive dashboard, chat window, and interactive "What-If" scenario tool.

## Prerequisites

- Python 3.9+
- An active `ANTHROPIC_API_KEY` for Claude model generation. Installation of the `flask` and `requests` python libraries.

## How to Run

1. **Install Requirements:**
   Make sure you have `flask` and `requests` installed by running:
   ```bash
   pip3 install flask requests
   ```

2. **Set Environment Variables:**
   You must configure your Anthropics API key in the environment before booting up the application to enable the Chat features.
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

3. **Start the Flask Server:**
   Execute the main entrypoint.
   ```bash
   python3 app_v3.py
   ```
   The application will start the development server on `http://127.0.0.1:7000/`.

4. **Open in Browser:**
   Navigate to `http://localhost:7000` in your web browser to view the interactive application!