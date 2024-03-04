import gitlab, gitlab.const, os, subprocess, concurrent.futures, configparser, re, string, csv, shutil, requests
from typing import Final
from gitlab.v4 import objects
from datetime import datetime

requests.packages.urllib3.disable_warnings()

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

            if 'forceReDownload' in parser['gitlab'] and parser['gitlab']['forceReDownload'] == 'yes':
                data['gitlab']['forceReDownload'] = True
            else:
                data['gitlab']['forceReDownload'] = False
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
        print('(' + datetime.now().strftime('%d-%m-%Y %I:%M:%S %p') + ') [' + self.project['name'] + ']:', *args, **kwargs)

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

# updateGitObjects
def updateGitObjects(logger: ProjectImportLogger):
    commands = [
        'git fsck',
        'git prune',
        'git repack',
        'git fsck',
    ]

    logger.print('Updating Git objects...')

    for command in commands:
        logger.print(f'Running "{command}"...')

        cmdSuccess = executeCommand(command)

        if not cmdSuccess:
            logger.print('Command failed.')

            return False

    return True

# updateGitObjects

# repoURLToName
def repoURLToName(url):
    return url.split(':')[-1].split('/')[-1].split('.git')[0]

# repoURLToName

# preImportCheck
def preImportCheck(config: dict, project: dict, gitlabInstance: gitlab.Gitlab, logger: ProjectImportLogger):
    projectName = repoURLToName(project['projectLink'])
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
        logger.print(f'Import of {projectName} is already started.')

        return False
    else:
        # isProjectImported = False

        # Check if project is already created in GitLab
        for glProject in gitlabInstance.projects.list(all = True):
            if glProject.name == projectName:
                # Check if project in GitLab is empty
                if len(glProject.branches.list()) == 0:
                    shouldCreateProject = False
                    glProjectInstance = glProject

                    logger.print(f'Project: {projectName} was created in GitLab but, is empty.')

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

    return (config, project, gitlabInstance, glProjectInstance)

# preImportCheck

# importProject
def importProject(config: dict, project: dict, gitlabInstance: gitlab.Gitlab, isModule: bool = False):
    cloneDirPath = os.path.join(APP_ROOT_DIR, TEMP_CLONE_DIR)
    projectDirPath = os.path.join(cloneDirPath, project['name'])

    logger = ProjectImportLogger(project)

    if not os.path.isdir(cloneDirPath):
        os.mkdir(cloneDirPath)

    checkResult = preImportCheck(config, project, gitlabInstance, logger)

    if not checkResult:
        return logger.rtn(False)

    config, project, gitlabInstance, glProjectInstance = checkResult

    gitlabProjectURL = glProjectInstance.ssh_url_to_repo

    if 'useHTTPToMoveCode' in config['gitlab'] and config['gitlab']['useHTTPToMoveCode']:
        gitlabProjectURL = glProjectInstance.http_url_to_repo
        gitlabProjectURLPrefix = config['gitlab']['adminUser'] + ':' + config['gitlab']['accessToken'] + '@'

        if gitlabProjectURL.startswith('https://'):
            gitlabProjectURL = gitlabProjectURL.replace('https://', 'https://' + gitlabProjectURLPrefix)
        elif gitlabProjectURL.startswith('http://'):
            gitlabProjectURL = gitlabProjectURL.replace('http://', 'http://' + gitlabProjectURLPrefix)

    if config['gitlab']['forceReDownload']:
        if os.path.isdir(projectDirPath):
            logger.print('Removing previously downloaded copy...')

            shutil.rmtree(projectDirPath)

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

    # Check and process Child repos first
    logger.print('Checking if project has modules...')

    gitModulesFile = os.path.join(projectDirPath, '.gitmodules')
    modulesImported = 0

    if os.path.isfile(gitModulesFile):
        modulesParser = configparser.ConfigParser()
        modulesParser.read(gitModulesFile)

        for mSec in modulesParser.sections():
            if mSec.startswith('[submodule'):
                module = {
                    'projectLink': modulesParser[mSec]['url'],
                    'isModule': True,
                    'branch': modulesParser[mSec]['branch'],
                }
                mName = repoURLToName(module['projectLink'])

                logger.print(f'Beginning process of {mName} module...')

                result = importProject(config, module, gitlabInstance, True)
                isImported = False

                if result:
                    mName, success, newRepoURL = result

                    if success:
                        logger.print('Updating Git modules file...')

                        with open(gitModulesFile, 'r+') as fpGitModule:
                            fpGitModule.write( fpGitModule.read().replace( module['projectLink'], newRepoURL ) )

                        modulesImported += 1

                if not isImported:
                    logger.print('Unable to import Git module.')

                    return logger.rtn(False)

    if modulesImported > 0:
        if not executeCommand('git add .gitmodules && git commit -m "Modules imported"'):
            logger.print('Unable to commit the modules update.')

            return logger.rtn(False)

    branches = executeCommand('git branch -r')

    if not branches:
        logger.print('Unable to get the branches')

        return logger.rtn(False)
    else:
        _, branches = branches

        branches = [branch.strip() for branch in branches.split('\n') if branch.strip().startswith('origin/')]
        processedBranches = []

        # To avoid git track error, exclude local branches:
        localBranches = executeCommand('git branch')

        if localBranches:
            _, localBranches = localBranches

            for localBranch in localBranches.split('\n'):
                localBranch = localBranch.strip()

                if localBranch.startswith('*'):
                    localBranch = localBranch.split(' ')[1]

                if localBranch:
                    processedBranches.append(localBranch)

        # Iterate branches
        for branch in branches:
            if branch.startswith('origin/HEAD'):
                branch = branch.split(' ')[-1]

            if branch.startswith('*') or branch in processedBranches:
                pass
            else:
                branch = branch.replace('origin/', '', 2)

                if branch in processedBranches:
                    continue

                logger.print(f'Tracking branch: {branch}...')

                isBranchTracked = executeCommand(f'git branch --track {branch} origin/{branch}')

                if not isBranchTracked:
                    logger.print('Unable to track branch')

                    return logger.rtn(False)

                processedBranches.append(branch)
        # Iterate branches

        logger.print('Updating downloaded repository...')

        isFetched = executeCommand('git fetch --all')

        if not isFetched:
            logger.print('Unable to update repository')

            return logger.rtn(False)

        logger.print('Merging changes to downloaded repository...')

        isPulled = executeCommand('git pull --all')

        if not isPulled:
            logger.print('Unable to merge changes')

            return logger.rtn(False)

        logger.print('Uploading code to GitLab...')

        isCodePushed = executeCommand('git push --set-upstream gitlab --all')

        if not isCodePushed:
            logger.print('Unable to upload code to GitLab')

            return logger.rtn(False)

        logger.print('Uploading tags to GitLab...')

        isTagsPushed = executeCommand('git push --set-upstream gitlab --tags')

        if not isTagsPushed:
            logger.print(f'Unable to upload tags to GitLab.')

            return logger.rtn(False)

    logger.print(f'Assigning users to the project...')

    if 'maintainers' in project:
        addUsersToProject(project['maintainers'].split(','), gitlab.const.AccessLevel.MAINTAINER, logger, gitlabInstance, glProjectInstance)

    if 'developers' in project:
        addUsersToProject(project['developers'].split(','), gitlab.const.AccessLevel.DEVELOPER, logger, gitlabInstance, glProjectInstance)

    if 'testers' in project:
        addUsersToProject(project['testers'].split(','), gitlab.const.AccessLevel.REPORTER, logger, gitlabInstance, glProjectInstance)

    # Remove project from processing entries
    with open(os.path.join(APP_ROOT_DIR, PROCESSING_RECORD_FILE), 'w+') as fpProcessing:
        fpProcessing.write(fpProcessing.read().strip().replace(project['name'], '').strip())

    return logger.rtn(True, gitlabProjectURL)

# importProject

# main
def main():
    config = getConfigData()

    projects = getProjectsList(config['projectsListFile'])

    if projects and len(projects) > 0:
        gitSSHCommand = 'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no'

        if 'keyFile' in config['gitlab'] and config['gitlab']['keyFile']:
            gitSSHCommand += ' -i ' + config['gitlab']['keyFile']

        executeCommand(f'git config --global core.sshCommand "{gitSSHCommand}"')

        gitlabInstance = gitlab.Gitlab(config['gitlab']['baseURL'], private_token = config['gitlab']['accessToken'], ssl_verify = False)

        # Thread pool executor
        with concurrent.futures.ThreadPoolExecutor(max_workers = MAX_THREAD_SIZE) as executor:
            threads = []

            # Iterate projects to Import
            for project in projects:
                # Start import process as a thread
                threads.append(executor.submit(importProject, config, project, gitlabInstance))

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
