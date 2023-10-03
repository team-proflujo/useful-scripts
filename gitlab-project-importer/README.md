# GitLab projects importer

This script takes list of projects from various sources (Git based) and imports into GitLab instance.

## Setup

- `sudo apt-get install -y python3-venv`
- `python3.10 -m venv venv`
- `sudo chmod -R 777 venv`
- `source "venv/bin/activate"`
- `pip install --upgrade pip`
- `pip install python-gitlab`

## Run

- Change config variables inside the script and execute command:
    - `source "venv/bin/activate"`
    - `python gitlab-import-project.py`
