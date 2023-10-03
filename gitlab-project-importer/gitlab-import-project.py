import gitlab, sys, os, subprocess, concurrent.futures

# executeCommand
def executeCommand(cmd):
    cmdResult = subprocess.run(cmd, capture_output = True, text = True, shell = True)

    if cmdResult and cmdResult.returncode == 0:
        return cmdResult.stdout or True
    else:
        print(cmdResult.stderr if cmdResult and cmdResult.returncode != 0 else 'Command failed to execute.')

    return False

# executeCommand

# Replace with your GitLab instance URL and access token
gitlab_url = ''
gitLabAdminUser = ''
access_token = ''

argv_path = 'projectsList.txt'
source_inputs = None

# Open the text file for reading
with open(argv_path, 'r') as file:
    # Read all lines from the file into a list
    source_inputs = file.readlines()

if source_inputs and len(source_inputs) > 0:
    if not(gitlab_url and len(gitlab_url) > 0 and gitLabAdminUser and len(gitLabAdminUser) > 0 and access_token and len(access_token) > 0):
        print('GitLab site credentials are not provided.')
        quit()

    #for threading
    threads = []
    # Create a GitLab API client
    gl = gitlab.Gitlab(gitlab_url, private_token=access_token)

    # Now, user_inputs is a list containing the lines from the text file.
    # You can process the user inputs as needed.
    for url in source_inputs:
        # Process each line (input) from the file
        url = url.strip()  # Remove leading/trailing whitespace or newline characters
        print(f"Project URL: {url}")

        fields = str.split(url,"/")
        sourceFileName = fields[len(fields) - 1]
        projectFileSplit = str.split(sourceFileName,".")
        projectName = projectFileSplit[0]

        screenCheck = executeCommand(f'screen -list | grep "{projectName}"')

        if screenCheck and len(screenCheck.strip()) > 0:
            print(f'Import of {projectName} is already started.')
            continue
        else:
            projectAlreadyCreated = False

            for project in gl.projects.list():
                if project.name == projectName:
                    projectAlreadyCreated = True
                    break

            if projectAlreadyCreated:
                print(f'Project: {projectName} already imported to GitLab.')
                continue

        project = gl.projects.create({'name': projectName, 'namespace': gitLabAdminUser})
        new_project_url = project.http_url_to_repo
        new_project_url = new_project_url.replace("http://", f"http://{gitLabAdminUser}:{access_token}@")
        cmd = f"screen  -S {projectName} -dm -L -Logfile {projectName}.log  bash -c 'bash cloneProject.sh {url} {projectName} {new_project_url}'"
        threads.append(cmd)

    # Create a ThreadPoolExecutor with a specified number of worker threads
    max_workers = 3  # Number of worker threads in the pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks for execution
        futures = [executor.submit(executeCommand, i) for i in threads]

        # Retrieve results as they become available
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            print(result)
