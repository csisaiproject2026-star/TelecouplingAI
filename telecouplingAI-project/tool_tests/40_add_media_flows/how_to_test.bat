        @echo off
        REM ================================================================
        REM  Tool: Add Media Flows
        REM  Tool call name: run_add_media_flows
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
        REM      "Prompt: add media flows, html_file=article.html, source_lon=116.4, source_lat=39.9, country_reference_csv=country_centroids.csv"
        REM   5. Outputs will appear in output/ after the run completes
        REM
        REM Option B — standalone Python (non-InVEST tools only):
        REM   conda activate TeleCouplingAI
        REM   cd ..\..\backend
        REM   python -c "
        REM     import asyncio, sys, os
        REM     sys.path.insert(0, os.getcwd())
        REM     from tools.media_flows import *
        REM     # See SKILL.md for exact parameter format
        REM   "
        REM
        REM INPUT FILES
        REM -----------
        REM Upload: testdata/article.html, testdata/country_centroids.csv
Prompt: add media flows, html_file=article.html, source_lon=116.4, source_lat=39.9, country_reference_csv=country_centroids.csv
        REM
        REM OUTPUT FILES go to: output/
        REM ================================================================
        echo Test guide for: Add Media Flows
        echo.
        echo See comments above for test instructions.
        echo Input files are in testdata/
        echo Outputs will be written to output/
        pause
