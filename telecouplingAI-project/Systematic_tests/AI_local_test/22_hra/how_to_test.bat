        @echo off
        REM ================================================================
        REM  Tool: Habitat Risk Assessment (HRA)
        REM  Tool call name: run_habitat_risk_assessment
        REM  Category: InVEST (natcap.invest)
        REM ================================================================
        REM
        REM HOW TO TEST
        REM -----------
        REM Option A — via the web UI (recommended):
        REM   1. Start the platform:  cd .. && docker compose up -d
        REM   2. Open http://localhost in your browser
        REM   3. Upload files from the testdata/ folder
        REM   4. Send a chat message like:
        REM      "Prompt: run habitat risk assessment, info_csv=criteria_info.csv"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.hra import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Requires: info CSV (pointing to habitat/stressor CSVs and TIFs), criteria scores CSVs
Prompt: run habitat risk assessment, info_csv=criteria_info.csv
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Habitat Risk Assessment (HRA)
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
