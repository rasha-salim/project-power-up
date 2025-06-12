# Set Python path to include current directory
$env:PYTHONPATH = "."

# Load environment variables from .env file
Write-Host "Loading environment variables from .env file..."

# Run the test script directly
Write-Host "Running Anthropic integration test..."
python -c "import os; from dotenv import load_dotenv; load_dotenv(); from app.tests.test_crewai_anthropic import run_test; run_test()"

# Check the exit code
if ($LASTEXITCODE -eq 0) {
    Write-Host "\nTest script completed with exit code: $LASTEXITCODE"
} else {
    Write-Host "\nTest script failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}
