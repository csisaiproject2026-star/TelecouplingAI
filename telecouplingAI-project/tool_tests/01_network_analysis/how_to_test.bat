        @echo off
        REM ================================================================
        REM  Tool: Network Analysis Grouping
        REM  Tool call name: run_network_analysis_grouping
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
        REM      "Prompt: run network community analysis, Node ID=CODE, sender=sender, receiver=receiver, weight=larrivals, join=ISO_3_CODE, algo=walktrap"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.analysis import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: nodes.csv, links.csv, World_countries_2002.shp/.dbf/.shx/.prj
Data path: ../datainput_for_demo/NetworkAnalysisGrouping_input/
Prompt: run network community analysis, Node ID=CODE, sender=sender, receiver=receiver, weight=larrivals, join=ISO_3_CODE, algo=walktrap
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Network Analysis Grouping
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
