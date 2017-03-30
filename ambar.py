#!/usr/bin/env python3
# Ambar Installation Script (Python 3)
# https://ambar.cloud

import argparse
import subprocess
import os
import json
import time

AMBAR_LOGO = """ 

______           ____     ______  ____       
/\  _  \  /'\_/`\/\  _`\  /\  _  \/\  _`\    
\ \ \L\ \/\      \ \ \L\ \\ \ \L\ \ \ \L\ \  
 \ \  __ \ \ \__\ \ \  _ <'\ \  __ \ \ ,  /   
  \ \ \/\ \ \ \_/\ \ \ \L\ \\ \ \/\ \ \ \\ \  
   \ \_\ \_\ \_\\ \_\ \____/ \ \_\ \_\ \_\ \_\\
    \/_/\/_/\/_/ \/_/\/___/   \/_/\/_/\/_/\/ /


                                              """

VERSION = '0.0.1'
STATIC_FILE_HOST = 'https://static.ambar.cloud/'
BLOG_HOST = 'https://blog.ambar.cloud/'
START = 'start'
STOP = 'stop'
INSTALL = 'install'
UPDATE = 'update'
RESTART = 'restart'

PATH = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser(description='Ambar Installation Script (https://ambar.cloud)')

parser.add_argument('action', choices=[INSTALL, START, STOP, RESTART, UPDATE])
parser.add_argument('--version', action='version', version = VERSION)
parser.add_argument('--useLocalConfig', action='store_true', help = 'use config.json from the script directory')
parser.add_argument('--configUrl', default = '{0}config.json'.format(STATIC_FILE_HOST), help = 'url of configuration file')

args = parser.parse_args()

def runShellCommandStrict(command):
     subprocess.check_call(command, shell = True)

def runShellCommand(command):
     return subprocess.call(command, shell = True)

def checkRequirements():
    # Check That Docker Installed
    if (runShellCommand('docker -v') != 0):
        print('docker is not installed. Check Ambar requirements here: {0}'.format(BLOG_HOST))
        exit(-1)

    # Check That Docker-Compose Installed
    if (runShellCommand('docker-compose -v') != 0):
        print('docker-compose is not installed. Check Ambar requirements here: {0}'.format(BLOG_HOST))
        exit(-1)

    # Check That Running Under Sudo
    if (os.geteuid() != 0):
        print('Please run this script as root user')
        exit(-1)

def getMachineIpAddress():
    ipAddress = subprocess.check_output("echo $(ip route get 8.8.8.8 | head -1 | cut -d' ' -f8)", shell=True)
    return str(ipAddress.decode("utf-8").replace('\n', ''))

def writeOsConstantIfNotExist(sysConfig, writeDescriptor, key, value):
    if (sysConfig.find(key) == -1):
        writeDescriptor.write("{0}={1}\n".format(key,value))
    
def setOsConstants():
    sysConfig = None
    with open('/etc/sysctl.conf', 'r') as sysConfigFile:
        sysConfig = sysConfigFile.read()
    
    with open('/etc/sysctl.conf', 'a') as sysConfigFile:
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'vm.max_map_count', '262144')
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'net.ipv4.ip_local_port_range', '"15000 61000"')
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'net.ipv4.tcp_fin_timeout', '30')
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'net.core.somaxconn', '1024')
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'net.core.netdev_max_backlog', '2000')
        writeOsConstantIfNotExist(sysConfig, sysConfigFile, 'net.ipv4.tcp_max_syn_backlog', '2048')        
        
def setRunTimeOsConstants():
    runShellCommandStrict('sysctl -w vm.max_map_count=262144')
    runShellCommandStrict('sysctl -w net.ipv4.ip_local_port_range="15000 61000"')
    runShellCommandStrict('sysctl -w net.ipv4.tcp_fin_timeout=30')
    runShellCommandStrict('sysctl -w net.core.somaxconn=1024')
    runShellCommandStrict('sysctl -w net.core.netdev_max_backlog=2000')
    runShellCommandStrict('sysctl -w net.ipv4.tcp_max_syn_backlog=2048')
        
def pullImages(configuration):
    dockerRepo = configuration['dockerRepo']

    runShellCommandStrict("docker pull {0}/ambar-crawler:latest".format(dockerRepo))
    runShellCommandStrict("docker pull {0}/ambar-pipeline:latest".format(dockerRepo))
    runShellCommandStrict("docker-compose -f {0}/docker-compose.yml pull".format(PATH))

def getDockerComposeTemplate():
    composeTemplate = None
    with open('{0}/docker-compose.template.yml'.format(PATH), 'r') as composeTemplateFile:
        composeTemplate = composeTemplateFile.read()
    return composeTemplate

def generateDockerCompose(configuration):        
    composeTemplate = getDockerComposeTemplate()

    composeTemplate = composeTemplate.replace('${DOCKER_REPO_URL}', configuration['dockerRepo'])
    
    composeTemplate = composeTemplate.replace('${DB_PATH}', '{0}/db'.format(configuration['dataPath']))
    composeTemplate = composeTemplate.replace('${ES_PATH}', '{0}/es'.format(configuration['dataPath']))
    composeTemplate = composeTemplate.replace('${RABBIT_PATH}', '{0}/rabbit'.format(configuration['dataPath']))

    composeTemplate = composeTemplate.replace('${FE_PORT}', configuration['fe']['port'])
    composeTemplate = composeTemplate.replace('${FE_HOST}', configuration['fe']['host'])
    composeTemplate = composeTemplate.replace('${FE_PROTOCOL}', configuration['fe']['protocol'])

    composeTemplate = composeTemplate.replace('${API_PORT}', configuration['api']['port'])
    composeTemplate = composeTemplate.replace('${API_PROTOCOL}', configuration['api']['protocol'])
    composeTemplate = composeTemplate.replace('${API_HOST}', configuration['api']['host'])
    composeTemplate = composeTemplate.replace('${PIPELINE_COUNT}', str(configuration['api']['pipelineCount']))
    composeTemplate = composeTemplate.replace('${CRAWLER_COUNT}', str(configuration['api']['crawlerCount']))
    composeTemplate = composeTemplate.replace('${ANALYTICS_TOKEN}', configuration['api'].get('analyticsToken', ''))
    composeTemplate = composeTemplate.replace('${DEFAULT_LANG_ANALYZER}', configuration['api']['defaultLangAnalyzer'])
    composeTemplate = composeTemplate.replace('${AUTH_TYPE}', configuration['api']['auth'])
    composeTemplate = composeTemplate.replace('${WEBAPI_CACHE_SIZE}', configuration['api']['cacheSize'])

    composeTemplate = composeTemplate.replace('${ES_HEAP_SIZE}', configuration['es']['heapSize'])
    composeTemplate = composeTemplate.replace('${ES_CONTAINER_SIZE}', configuration['es']['containerSize'])
    composeTemplate = composeTemplate.replace('${ES_CONTAINER_SIZE}', configuration['es']['containerSize'])

    composeTemplate = composeTemplate.replace('${OCR_PDF_MAX_PAGE_COUNT}', str(configuration['ocr']['pdfMaxPageCount']))
    composeTemplate = composeTemplate.replace('${OCR_PDF_SYMBOLS_PER_PAGE_THRESHOLD}', str(configuration['ocr']['pdfSymbolsPerPageThreshold']))
    
    composeTemplate = composeTemplate.replace('${DROPBOX_CLIENT_ID}', configuration['dropbox']['clientId'])
    composeTemplate = composeTemplate.replace('${DROPBOX_REDIRECT_URI}', configuration['dropbox']['redirectUri'])

    with open('{0}/docker-compose.yml'.format(PATH), 'w') as dockerCompose:
        dockerCompose.write(composeTemplate)    

def loadConfigFromFile():   
    with open('{0}/config.json'.format(PATH), 'r') as configFile:
        config = json.load(configFile)

    return config

def loadFromWeb():
    runShellCommandStrict('wget -O {0}/config.json {1}'.format(PATH, args.configUrl))
    return loadConfigFromFile()

def downloadDockerComposeTemplate():
    runShellCommandStrict('wget -O {0}/docker-compose.template.yml {1}'.format(PATH, configuration['dockerComposeTemplate']))

def install(configuration):                             
    downloadDockerComposeTemplate()
        
    machineAddress = getMachineIpAddress()
    configuration['api']['host'] = machineAddress
    configuration['fe']['host'] = machineAddress
    with open('{0}/config.json'.format(PATH), 'w') as configFile:
        json.dump(configuration, configFile, indent=4)

    generateDockerCompose(configuration)
    pullImages(configuration)
    setOsConstants()
    print('Ambar installed successfully! Run `sudo ambar.py start` to start Ambar')

def start(configuration):    
    setRunTimeOsConstants()    
    generateDockerCompose(configuration)
    runShellCommandStrict('docker-compose -f {0}/docker-compose.yml -p ambar up -d'.format(PATH))
    print('Waiting for Ambar to start...')
    time.sleep(30)
    print('Ambar is running on {0}://{1}:{2}'.format(configuration['fe']['protocol'], configuration['fe']['host'], configuration['fe']['port']))

def stop(configuration):
    dockerRepo = configuration['dockerRepo']
    print('Stopping Ambar...')               
    runShellCommand('docker rm -f $(docker ps -a -q --filter ancestor="{0}/ambar-crawler" --format="{{{{.ID}}}}")'.format(dockerRepo)) 
    print('Crawlers containers removed')
    runShellCommand('docker rm -f $(docker ps -a -q --filter ancestor="{0}/ambar-pipeline" --format="{{{{.ID}}}}")'.format(dockerRepo))
    print('Pipeline containers removed')
    runShellCommand('docker-compose -f {0}/docker-compose.yml -p ambar down'.format(PATH))
    print('Ambar is stopped')        

def update(configuration):    
    stop(configuration)
    downloadDockerComposeTemplate()
    generateDockerCompose(configuration)
    pullImages(configuration)
    start(configuration)

def restart(configuration):
    stop(configuration)
    start(configuration)

print(AMBAR_LOGO)
checkRequirements()

if (args.action == START):
    configuration = loadConfigFromFile()
    start(configuration)
    exit(0)

if (args.action == STOP):
    configuration = loadConfigFromFile()
    stop(configuration)
    exit(0)

if (args.action == RESTART):
    configuration = loadConfigFromFile()
    restart(configuration)
    exit(0)

if (args.action == INSTALL):
    if (args.useLocalConfig == True):
        configuration = loadConfigFromFile()    
    else:
        configuration = loadFromWeb()        

    install(configuration)
    exit(0)

if (args.action == UPDATE):
    configuration = loadConfigFromFile()
    update(configuration)
    exit(0)


