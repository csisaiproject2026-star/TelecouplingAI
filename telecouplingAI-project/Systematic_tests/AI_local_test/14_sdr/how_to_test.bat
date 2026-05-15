        @echo off
        REM ================================================================
        REM  Tool: Sediment Delivery Ratio (SDR)
        REM  Tool call name: run_Sediment_Delivery_Ratio_SDR
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
        REM      "Prompt: run sediment delivery ratio model"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.sdr import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Requires: DEM TIF, erosivity TIF, erodibility TIF, LULC TIF, watersheds SHP, biophysical table CSV
Prompt: run sediment delivery ratio model
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Sediment Delivery Ratio (SDR)
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
