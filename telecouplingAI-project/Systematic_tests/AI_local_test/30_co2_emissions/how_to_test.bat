        @echo off
        REM ================================================================
        REM  Tool: CO2 Emissions from Transport
        REM  Tool call name: run_co2_emissions
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
        REM      "Prompt: run CO2 emissions calculation, transport_distance_km=500, co2_per_km=2.6, capacity=50"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.emissions import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: testdata/co2_data.csv
Prompt: run CO2 emissions calculation, transport_distance_km=500, co2_per_km=2.6, capacity=50
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: CO2 Emissions from Transport
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
