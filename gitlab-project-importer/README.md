# GitLab projects importer

This script takes list of projects from various sources (Git based) and imports into GitLab instance.

## Setup

- `sudo ./setup.sh`

## Run

- Add your **SSH key** to the target GitLab instance
- `cp sample-importer.conf importer.conf`
- Change config variables inside `importer.conf` file, and Run:
    - `./run.sh`

## Import Template

To import the projects, the scripts needs a CSV file of the following format:

| Project | RW+ | RW | R |
|---------|-----|----|---|
|git@myserver.com:project1.git|ABC001,ABC002|ABC003|ABC004|
|git@myserver.com:project2.git|ABC0010,ABC0011|ABC0012|ABC0013|

- In the CSV file, the First column in each row must have the valid **Git URL** to the Project that we are importing.
- The Second column should contains the Usernames to who the **Maintainer** role should be given for the Project.
- The Third column should contains the Usernames to who the **Developer** role should be given for the Project.
- The Third column should contains the Usernames to who the **Reporter** role should be given for the Project.

**NOTE: LDAP users are not stored into GitLab before their first time Login. So, A LDAP user cannot be assigned to the Project unless they have logged in before**
