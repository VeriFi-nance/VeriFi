
# 🔍 AI Claim Extractor (Agno & LM Studio)

This project is a privacy-focused AI tool that uses a local Large Language Model (LLM) to extract **"Hard Claims"** from text. It specifically identifies verifiable claims by isolating three key csomponents: **Time Frame**, **Quantity**, and **Subject/Object**.



## ✨ Features

* **100% Local Processing:** Integration with LM Studio ensures your data never leaves your machine.
* **Automatic Language Detection:** Seamlessly detects and processes sentences in multiple languages, including English and Turkish.
* **Multi-Claim Analysis:** Capable of splitting complex sentences into multiple independent claim objects.
* **Error-Tolerant Schema:** Uses Pydantic `Alias` mapping to automatically handle common typos made by smaller LLMs (e.g., `detectected_language`).

## 🛠️ Setup

### 1. LM Studio Configuration
1.  Open LM Studio and load an Instruct model (Recommended: `Llama-3-8B-Instruct`).
2.  Navigate to the **Local Server** tab (`>_` icon).
3.  In the right panel, set the **Response Format** to `json_object`.
4.  Click **Start Server** to host the API at `localhost:1234`.

### 2. Python Environment
Navigate to your project folder in the terminal and run the following commands:

```bash
# Create a virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

## 🚀 Usage

With the virtual environment activated, start the application:

```bash
python main.py

```

* **Analyze:** Enter any sentence and press Enter.
* **Exit:** Type `exit` to close the program.

## 📂 File Structure

* `main.py`: Handles the user interface loop, regex cleaning logic, and Agno Agent configuration.
* `schema.py`: Defines data validation rules and Pydantic models.
* `requirements.txt`: Lists the required Python libraries.

## 📝 Example Scenario

**Input:** *"I predict Bitcoin will hit $100,000 by the end of 2026."*

**Output:**

* ✅ **Language:** en
* **Claim:** Bitcoin will hit $100,000 by the end of 2026
* **Subject:** Bitcoin
* **Quantity:** $100,000
* **Time Frame:** end of 2026


