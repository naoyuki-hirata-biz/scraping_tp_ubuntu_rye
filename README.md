# scraping_tp_ubuntu_rye
scraping tp

## Usage
```
. .venv/bin/activate
rye sync
rye run playwright install-deps
rye run playwright install chromium firefox
rye run python src/scraping_tp_ubuntu_rye/scraping_tp.py --keyword 介護 --driver-path=/usr/bin/chromedriver
```
