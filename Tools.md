# clean local cache
cd finance

git fetch origin

git reset --hard origin/main


# start ui
cd asset_report

python3 -m asset_report --ui