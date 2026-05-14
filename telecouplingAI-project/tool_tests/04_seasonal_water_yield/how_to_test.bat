        @echo off
        REM ================================================================
        REM  Tool: Seasonal Water Yield
        REM  Tool call name: run_seasonal_water_yield
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
        REM      "Prompt: run seasonal water yield model with the uploaded files"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.water_yield import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: all files in SeasonalWaterYield_input/
Data path: ../datainput_for_demo/SeasonalWaterYield_input/
Prompt: run seasonal water yield model with the uploaded files
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Seasonal Water Yield
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
