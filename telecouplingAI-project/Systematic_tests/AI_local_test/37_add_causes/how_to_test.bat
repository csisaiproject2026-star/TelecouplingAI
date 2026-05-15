        @echo off
        REM ================================================================
        REM  Tool: Add Causes Interactively
        REM  Tool call name: run_add_causes_interactively
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
        REM      "Prompt: add causes from causes.csv, x_col=longitude, y_col=latitude, description_col=cause_description"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.causes import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: testdata/causes.csv
Prompt: add causes from causes.csv, x_col=longitude, y_col=latitude, description_col=cause_description
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Add Causes Interactively
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
