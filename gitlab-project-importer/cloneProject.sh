#!/bin/bash

sleep 10s

mkdir -p clonedProjects

data=$(cd clonedProjects && git clone "$1")

updateUrl=$(cd clonedProjects/"$2" && git remote add gitlab "$3")

cd clonedProjects/"$2"

branchList=$(git branch -a)
IFS=$'\n'
find_data="origin/HEAD"

for line in $branchList; do
    split_by_space=($line)
    data=()
    for test in "${split_by_space[@]}"; do
        # Remove "remotes", spaces, and "origin" from the branch name
        branch_name=$(echo "$test" | sed -e 's/remotes//' -e 's/origin//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/.*\///')
        data+=("$branch_name")
    done

    if (echo "$line" | grep -q "$find_data") || (echo "$line" | grep -q "*"); then
        echo "True"
    else
        for branch in "${data[@]}"; do
            if [ -n "$branch" ]; then
                git switch $branch
                git pull
                git push --all gitlab
                git push --tags gitlab
            fi
        done
    fi
done

cd clonedProjects/$2 && git remote rm origin
cd clonedProjects/$2 && git remote rename gitlab origin
cd clonedProjects/ && rm -rf "$2"