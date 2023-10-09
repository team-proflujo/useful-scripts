#!/bin/bash

if [ "`id -u`" != "0" ]
then
    echo "Please run this script as a sudo user."
    exit 1
fi

sudo apt-get install git python3 python3-pip python3-venv -y

python3 -m venv venv

sudo chmod -R 777 venv

source "venv/bin/activate"

pip install --upgrade pip

pip install python-gitlab
