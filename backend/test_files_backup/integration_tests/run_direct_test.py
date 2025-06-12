import os
import sys
import logging
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from app.tools.document_search import DocumentSearchTool

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_anthropic_integration():
    """
    Test the integration between CrewAI and Anthropic using ChatAnthropic
    """
    print("\n===== TESTING CREWAI-ANTHROPIC INTEGRATION =====\n")
    
    # Check if Anthropic API key is set
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment variables")
        logger.error("ANTHROPIC_API_KEY not found in environment variables")
        return False
    else:
        print(f"✅ ANTHROPIC_API_KEY found (length: {len(anthropic_api_key)})")
    
    try:
        # Step 1: Initialize ChatAnthropic
        print("\n📋 Step 1: Initializing ChatAnthropic...")
        llm = ChatAnthropic(
            model_name="claude-3-haiku-20240307",
            temperature=0.2,
            anthropic_api_key=anthropic_api_key,
            max_tokens=1000
        )
        print("✅ ChatAnthropic initialized successfully")
        
        # Step 2: Create an agent
        print("\n📋 Step 2: Creating test agent...")
        agent = Agent(
            role="Technical Analyst",
            goal="Analyze project requirements and provide technical recommendations",
            backstory="You are an experienced technical architect with expertise in software design.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )
        print("✅ Agent created successfully")
        
        # Step 3: Create a task
        print("\n📋 Step 3: Creating test task...")
        task = Task(
            description="Analyze the following project requirements and provide a brief technical recommendation: 'Build a web application for project management with document upload capabilities.'",
            expected_output="A brief technical recommendation",
            agent=agent
        )
        print("✅ Task created successfully")
        
        # Step 4: Create a crew
        print("\n📋 Step 4: Creating crew...")
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
            process=Process.sequential
        )
        print("✅ Crew created successfully")
        
        # Step 5: Execute the crew
        print("\n📋 Step 5: Executing crew... (this may take a minute)")
        logger.info("Executing crew...")
        result = crew.kickoff()
        
        # Print the result
        print(f"\n✅ RESULT:\n{'-'*50}\n{result}\n{'-'*50}\n")
        logger.info(f"Result: {result}")
        print("\n===== CREWAI-ANTHROPIC INTEGRATION TEST COMPLETED SUCCESSFULLY =====\n")
        return True
    
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        logger.error(f"Error testing Anthropic integration: {e}")
        import traceback
        trace = traceback.format_exc()
        print(f"\nTraceback:\n{trace}")
        logger.error(f"Traceback: {trace}")
        print("\n===== CREWAI-ANTHROPIC INTEGRATION TEST FAILED =====\n")
        return False

if __name__ == "__main__":
    """Run the test when the script is executed directly"""
    try:
        success = test_anthropic_integration()
        if success:
            print("✅ Integration test completed successfully!")
            sys.exit(0)
        else:
            print("❌ Integration test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)