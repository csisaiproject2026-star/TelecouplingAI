        # Test Data — Network Analysis Grouping

        This InVEST tool uses demo data from the shared directory:

            ../../../datainput_for_demo/

        Upload: nodes.csv, links.csv, World_countries_2002.shp/.dbf/.shx/.prj
Data path: ../datainput_for_demo/NetworkAnalysisGrouping_input/
Prompt: run network community analysis, Node ID=CODE, sender=sender, receiver=receiver, weight=larrivals, join=ISO_3_CODE, algo=walktrap

        ## Notes
        - InVEST tools require real geospatial data (TIF, SHP) and cannot be tested
          with minimal synthetic CSVs.
        - For quick testing, upload the demo files to the web UI and send the prompt
          shown in how_to_test.bat.
        - Full InVEST sample datasets are available at:
          https://storage.googleapis.com/releases.naturalcapitalproject.org/invest-sample-data/
