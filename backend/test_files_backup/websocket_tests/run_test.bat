@echo off
echo Running Anthropic integration test...
call venv\Scripts\activate
python direct_test.py > test_output.log 2>&1
echo Test completed. Check test_output.log for results.
