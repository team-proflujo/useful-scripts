import gitlab, gitlab.const, os, subprocess, concurrent.futures, configparser, re, string, time, csv, shutil
from typing import Final
from gitlab.v4 import objects

APP_ROOT_DIR: Final = os.path.abspath(os.path.dirname( __file__ )).rstrip('/\\')
MAX_THREAD_SIZE: Final = 1
CONFIG_FILE: Final = 'importer.conf'
TEMP_CLONE_DIR: Final = 'clonedProjects'
PROCESSING_RECORD_FILE: Final = '.processing'

# executeCommand
def executeCommand(cmd):
    cmdResult = subprocess.run(cmd, capture_output = True, text = True, shell = True)

    if cmdResult and cmdResult.returncode == 0:
        return True, (cmdResult.stdout or True)
    else:
        print(cmdResult.stderr if cmdResult and cmdResult.returncode != 0 else 'Command failed to execute.')

    return False

# executeCommand

# getConfigData
def getConfigData():
    data = {}
    errors = []
    configFile = os.path.join(APP_ROOT_DIR, CONFIG_FILE)

    if os.path.isfile(configFile):
        parser = configparser.ConfigParser()
        parser.read(configFile)

        if 'general' in parser:
            if 'projectsListFile' in parser['general'] and parser['general']['projectsListFile']:
                data['projectsListFile'] = parser['general']['projectsListFile']
            else:
                errors.append('Invalid "projectsListFile" option in "general" section.')
        else:
            errors.append('"general" config options not found.')

        if 'gitlab' in parser:
            data['gitlab'] = {}

            if 'baseURL' in parser['gitlab'] and parser['gitlab']['baseURL']:
                data['gitlab']['baseURL'] = parser['gitlab']['baseURL']
            else:
                errors.append('Invalid "baseURL" option in "gitlab" section.')

            if 'adminUser' in parser['gitlab'] and parser['gitlab']['adminUser']:
                data['gitlab']['adminUser'] = parser['gitlab']['adminUser']
            else:
                errors.append('Invalid "adminUser" option in "gitlab" section.')

            if 'accessToken' in parser['gitlab'] and parser['gitlab']['accessToken']:
                data['gitlab']['accessToken'] = parser['gitlab']['accessToken']
            else:
                errors.append('Invalid "accessToken" option in "gitlab" section.')

            if 'keyFile' in parser['gitlab'] and parser['gitlab']['keyFile']:
                data['gitlab']['keyFile'] = parser['gitlab']['keyFile']

            if 'useHTTPToMoveCode' in parser['gitlab'] and parser['gitlab']['useHTTPToMoveCode'] == 'yes':
                data['gitlab']['useHTTPToMoveCode'] = True
        else:
            errors.append('"gitlab" config options not found.')
    else:
        errors.append('The config file does not exists or is unreadable.')

    if len(errors) > 0:
        print('Invalid config file:\n\t' + '\n\t'.join(errors))

        quit()

    return data

# getConfigData

# getProjectsList
def getProjectsList(projectsListFile):
    CSV_COLUMNS: Final = [
        {
            'name': 'projectLink',
            'heading': 'Project',
            'required': True,
        },
        {
            'name': 'maintainers',
            'heading': 'RW+',
            'required': False,
        },
        {
            'name': 'developers',
            'heading': 'RW',
            'required': False,
        },
        {
            'name': 'testers',
            'heading': 'R',
            'required': False,
        },
    ]
    ALPHABETS: Final = list(string.ascii_uppercase)
    projects = []

    if os.path.isfile(projectsListFile):
        with open(projectsListFile, 'r') as fpProjects:
            projectsFileContent = [ line for line in csv.reader(fpProjects) if len(line) > 0 ]

            if projectsFileContent and len(projectsFileContent) > 0:
                headingRow = projectsFileContent[0]
                contentRows = projectsFileContent[1:]
                errors = {}

                # Validate heading row
                for colIndex, col in enumerate(CSV_COLUMNS):
                    if colIndex < len(headingRow) and headingRow[colIndex] == col['heading']:
                        pass
                    else:
                        if not('Row #1' in errors):
                            errors['Row #1'] = []

                        errors['Row #1'].append('Column ' + ALPHABETS[colIndex] + ' should be "' + col['heading'] + '".')

                # Validate data rows
                for rowIndex, row in enumerate(contentRows):
                    rowErrKey = f'Row #{rowIndex + 2}'
                    rowErrors = []
                    projectData = {}

                    # Iterate all columns in the row
                    for colIndex, col in enumerate(CSV_COLUMNS):
                        colErr = None

                        if colIndex < len(row) and row[colIndex]:
                            # Validate project URL
                            if col['name'] == 'projectLink':
                                if re.match(r'^http(s?)\:\/\/.+\.git$', row[colIndex]):
                                    if row[colIndex].startswith('https://'):
                                        projectData['sourceDomain'] = row[colIndex].split('https://')[1].split('/')[0]
                                    else:
                                        projectData['sourceDomain'] = row[colIndex].split('http://')[1].split('/')[0]
                                elif re.match(r'^.+\@.+\:.+\.git$', row[colIndex]):
                                    projectData['sourceDomain'] = row[colIndex].split('@')[1].split(':')[0]
                                else:
                                    colErr = 'Column ' + ALPHABETS[colIndex] + ' is invalid. It should be a valid Git URL. Refer: https://git-scm.com/docs/git-clone#URLS.'
                        else:
                               if col['required']:
                                    colErr = 'Column ' + ALPHABETS[colIndex] + ' is empty.'

                        if colErr:
                            rowErrors.append(colErr)
                        else:
                            projectData[col['name']] = row[colIndex]

                    if len(rowErrors) > 0:
                        errors[rowErrKey] = rowErrors
                    else:
                        projects.append(projectData)

                if len(errors) > 0:
                    print('There are some invalid data found:')

                    for rowIndex, rowErrors in errors.items():
                        print(f'\t{rowIndex}:')

                        for rowErr in rowErrors:
                            print(f'\t\t{rowErr}')

                    quit()
            else:
                print('There are projects provided to import.')
                quit()
    else:
        print('Invalid projects list file or the file is not readable.')
        quit()

    return projects

# getProjectsList

# logProjectImport
class ProjectImportLogger:
    project = None

    def __init__(self, project):
        self.project = project

    def print(self, *args, **kwargs):
        print('[' + self.project['name'] + ']:', *args, **kwargs)

    def rtn(self, *args):
        return (self.project['name'], *args)

# logProjectImport

# addUsersToProject
def addUsersToProject(users: list, accessLevel: gitlab.const.AccessLevel, logger: ProjectImportLogger, gitlabInstance: gitlab.Gitlab, glProjectInstance: objects.ProjectManager):
    users = [ user for user in users if user ]

    for user in users:
        user = user.strip()

        glUser = gitlabInstance.users.list(username = user)

        if len(glUser) == 0:
            logger.print(f'{user} does not exists on the GitLab instance.')

            continue
        else:
            glUser = glUser[0]

        glUserId = glUser.get_id()

        if len(glProjectInstance.members.list(user_ids = [glUserId])) > 0:
            logger.print(f'{user} is already in the project.')
        else:
            glMember = glProjectInstance.members.create({
                'user_id': glUserId,
                'access_level': accessLevel,
            })

            glMember.save()

# addUsersToProject

# importProject
def importProject(config: dict, project: dict, gitlabInstance: gitlab.Gitlab, glProjectInstance: objects.ProjectManager):
    cloneDirPath = os.path.join(APP_ROOT_DIR, TEMP_CLONE_DIR)
    logger = ProjectImportLogger(project)

    if not os.path.isdir(cloneDirPath):
        os.mkdir(cloneDirPath)

    projectDirPath = os.path.join(cloneDirPath, project['name'])
    gitSSHCommand = 'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no'
    gitlabProjectURL = glProjectInstance.ssh_url_to_repo

    if 'keyFile' in config['gitlab'] and config['gitlab']['keyFile']:
        gitSSHCommand += f' -i ' + config['gitlab']['keyFile']
    elif 'useHTTPToMoveCode' in config['gitlab'] and config['gitlab']['useHTTPToMoveCode']:
        gitlabProjectURL = glProjectInstance.http_url_to_repo
        gitlabProjectURLPrefix = config['gitlab']['adminUser'] + ':' + config['gitlab']['accessToken'] + '@'

        if gitlabProjectURL.startswith('https://'):
            gitlabProjectURL = gitlabProjectURL.replace('https://', 'https://' + gitlabProjectURLPrefix)
        elif gitlabProjectURL.startswith('http://'):
            gitlabProjectURL = gitlabProjectURL.replace('http://', 'http://' + gitlabProjectURLPrefix)

    if os.path.isdir(projectDirPath):
        logger.print('Project is already downloaded...')

        isCloned = True
    else:
        logger.print('Downloading...')

        isCloned = executeCommand('git clone ' + project['projectLink'] + ' ' + projectDirPath)

    if isCloned:
        os.chdir(projectDirPath)

        if executeCommand('git remote -v | grep -w "gitlab"'):
            isCloned = True
        else:
            isCloned = executeCommand('git remote add gitlab ' + gitlabProjectURL)

    if not isCloned:
        logger.print('Unable to download the project.')

        return logger.rtn(False)

    logger.print('Setting SSH options for git...')

    executeCommand(f'git config core.sshCommand "{gitSSHCommand}"')

    branches = executeCommand('git branch -r')

    if not branches:
        logger.print('Unable to get the branches')

        return logger.rtn(False)
    else:
        _, branches = branches

        branches = [branch.strip() for branch in branches.split('\n') if branch.strip().startswith('origin/')]

        # Iterate branches
        for branch in branches:
            if branch.startswith('*') or branch.startswith('origin/HEAD'):
                pass
            else:
                branch = branch.replace('origin/', '')

                isBranchSwitched = executeCommand(f'git switch {branch}')

                if not isBranchSwitched:
                    logger.print(f'Unable to switch to branch: {branch}')

                    return logger.rtn(False)

                isBranchPulled = executeCommand(f'git pull')

                if not isBranchPulled:
                    logger.print(f'Unable to get the code in {branch} branch.')

                    return logger.rtn(False)

                logger.print(f'Uploading branch: {branch} to GitLab...')

                isCodePushed = executeCommand(f'git push --all gitlab && git push --tags gitlab')

                if not isCodePushed:
                    logger.print(f'Unable to upload code in {branch} branch to GitLab. Ensure if you have added the "SSH Key" in the GitLab Instance.')

                    return logger.rtn(False)
        # Iterate branches

    logger.print(f'Assigning users to the project...')

    addUsersToProject(project['maintainers'].split(','), gitlab.const.AccessLevel.MAINTAINER, logger, gitlabInstance, glProjectInstance)

    addUsersToProject(project['developers'].split(','), gitlab.const.AccessLevel.DEVELOPER, logger, gitlabInstance, glProjectInstance)

    addUsersToProject(project['testers'].split(','), gitlab.const.AccessLevel.REPORTER, logger, gitlabInstance, glProjectInstance)

    # Remove project from processing entries
    with open(os.path.join(APP_ROOT_DIR, PROCESSING_RECORD_FILE), 'w+') as fpProcessing:
        fpProcessing.write(fpProcessing.read().strip().replace(project['name'], '').strip())

    logger.print('Cleaning up...')

    shutil.rmtree(projectDirPath)

    return logger.rtn(True)

# importProject

# main
def main():
    config = getConfigData()

    projects = getProjectsList(config['projectsListFile'])

    if projects and len(projects) > 0:
        executeCommand(f'git config --global core.sshCommand "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"')

        gitlabInstance = gitlab.Gitlab(config['gitlab']['baseURL'], private_token = config['gitlab']['accessToken'])

        # Thread pool executor
        with concurrent.futures.ThreadPoolExecutor(max_workers = MAX_THREAD_SIZE) as executor:
            threads = []

            # Iterate projects to Import
            for project in projects:
                projectName = project['projectLink'].split(':')[-1].split('/')[-1].split('.git')[0]
                isImporting = False
                shouldCreateProject = True
                glProjectInstance = None

                # Check if projects is being imported
                if os.path.isfile(os.path.join(APP_ROOT_DIR, PROCESSING_RECORD_FILE)):
                    with open(os.path.join(APP_ROOT_DIR, PROCESSING_RECORD_FILE), 'r') as fpProcessing:
                        for importingProject in fpProcessing.readlines():
                            if importingProject.strip() == projectName:
                                isImporting = True

                if isImporting:
                    print(f'Import of {projectName} is already started.')
                    continue
                else:
                    isProjectImported = False

                    # Check if project is already created in GitLab
                    for glProject in gitlabInstance.projects.list():
                        if glProject.name == projectName:
                            # Check if project in GitLab is empty
                            if len(glProject.branches.list()) == 0:
                                shouldCreateProject = False
                                glProjectInstance = glProject

                                print(f'Project: {projectName} was created in GitLab but, is empty.')
                            else:
                                isProjectImported = True

                            break

                    if isProjectImported:
                        print(f'Project: {projectName} was already imported into GitLab.')
                        continue

                # Mark the project import is started
                with open(os.path.join(APP_ROOT_DIR, PROCESSING_RECORD_FILE), 'a') as fpProcessing:
                    fpProcessing.write(f'\n{projectName}')

                # Create the project in GitLab if not already created
                if shouldCreateProject:
                    createdProject = gitlabInstance.projects.create({
                        'name': projectName,
                        'namespace': config['gitlab']['adminUser'],
                    })

                    glProjectInstance = createdProject

                project['name'] = projectName

                # Start import process as a thread
                threads.append(executor.submit(importProject, config, project, gitlabInstance, glProjectInstance))

            # Iterate projects to Import

            # Iterate thread results
            for thread in concurrent.futures.as_completed(threads):
                result = thread.result()

                if result:
                    project, imported = result

                    if imported:
                        print(f'{project} has been imported into GitLab successfully.')
                    else:
                        print(f'Failed to import {project}')

            # Iterate thread results

        # Thread pool executor

# main

# Run only when the script is directly executed
if __name__ == '__main__':
    main()
