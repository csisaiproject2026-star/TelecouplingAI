        @echo off
        REM ================================================================
        REM  Tool: OLS Model Selection
        REM  Tool call name: run_model_selection_ols
        REM  Category: Custom Python tool
        REM ================================================================
        REM
        REM HOW TO TEST
        REM -----------
        REM Option A — via the web UI (recommended):
        REM   1. Start the platform:  cd .. && docker compose up -d
        REM   2. Open http://localhost in your browser
        REM   3. Upload files from the testdata/ folder
        REM   4. Send a chat message like:
        REM      "Prompt: run OLS regression with dependent variable=y, independent variables=x1,x2,x3, run model selection"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.ols import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: testdata/ols_data.csv
Prompt: run OLS regression with dependent variable=y, independent variables=x1,x2,x3, run model selection
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: OLS Model Selection
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
