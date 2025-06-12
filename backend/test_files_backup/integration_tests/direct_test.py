import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Print environment information
print("\n===== ENVIRONMENT INFORMATION =====")
print(f"Python version: {sys.version}")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_api_key:
    print(f"ANTHROPIC_API_KEY: Found (length: {len(anthropic_api_key)})")
else:
    print("ANTHROPIC_API_KEY: Not found")

# Import CrewAI components
try:
    print("\n===== IMPORTING CREWAI =====")
    from crewai import Agent, Task, Crew, Process
    print("✅ CrewAI imported successfully")
except Exception as e:
    print(f"❌ Error importing CrewAI: {e}")
    sys.exit(1)

# Import Anthropic
try:
    print("\n===== IMPORTING ANTHROPIC =====")
    from langchain_anthropic import ChatAnthropic
    print("✅ ChatAnthropic imported successfully")
except Exception as e:
    print(f"❌ Error importing ChatAnthropic: {e}")
    sys.exit(1)

# Test Anthropic integration
def test_anthropic_integration():
    print("\n===== TESTING ANTHROPIC INTEGRATION =====")
    
    # Test each component separately to identify where the issue is
    
    # Step 1: Test direct Anthropic API call
    print("\n----- Step 1: Testing direct Anthropic API call -----")
    try:
        # Initialize ChatAnthropic
        print("Initializing ChatAnthropic...")
        llm = ChatAnthropic(
            model_name="claude-3-haiku-20240307",
            temperature=0.2,
            anthropic_api_key=anthropic_api_key,
            max_tokens=1000
        )
        print("✅ ChatAnthropic initialized successfully")
        
        # Test direct call to Anthropic
        print("Making direct call to Anthropic API...")
        response = llm.invoke("Hello, Claude! Please respond with a short greeting.")
        print(f"✅ Direct API call successful. Response: {response.content}")
    except Exception as e:
        print(f"❌ Error in direct Anthropic API call: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False
    
    # Step 2: Test Agent creation
    print("\n----- Step 2: Testing Agent creation -----")
    try:
        print("Creating test agent...")
        agent = Agent(
            role="Technical Analyst",
            goal="Analyze project requirements and provide technical recommendations",
            backstory="You are an experienced technical architect with expertise in software design.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )
        print("✅ Agent created successfully")
    except Exception as e:
        print(f"❌ Error creating Agent: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False
    
    # Step 3: Test Task creation
    print("\n----- Step 3: Testing Task creation -----")
    try:
        print("Creating test task...")
        task = Task(
            description="Analyze the following project requirements and provide a brief technical recommendation: 'Build a web application for project management with document upload capabilities.'",
            expected_output="A brief technical recommendation",
            agent=agent
        )
        print("✅ Task created successfully")
    except Exception as e:
        print(f"❌ Error creating Task: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False
    
    # Step 4: Test Crew creation
    print("\n----- Step 4: Testing Crew creation -----")
    try:
        print("Creating crew...")
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
            process=Process.sequential
        )
        print("✅ Crew created successfully")
    except Exception as e:
        print(f"❌ Error creating Crew: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False
    
    # Step 5: Test Crew execution
    print("\n----- Step 5: Testing Crew execution -----")
    try:
        print("Executing crew... (this may take a minute)")
        result = crew.kickoff()
        print(f"\n===== RESULT =====\n{result}\n")
        return True
    except Exception as e:
        print(f"❌ Error executing Crew: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_anthropic_integration()
    if success:
        print("\n✅ Anthropic integration test successful!")
        sys.exit(0)
    else:
        print("\n❌ Anthropic integration test failed!")
        sys.exit(1)
