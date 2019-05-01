#!/usr/bin/python

import sys

# check the python version needed ro run the script

if sys.version_info.major != 3 or sys.version_info[1] < 6:
    print("This script requires Python version 3.6")
    sys.exit(1)

from pyVmomi import vim, vmodl
from pyVim import connect
import requests
import jsbeautifier
import subprocess
import platform
import os
import argparse
import getpass
import atexit
import logging
from scp import SCPClient
import paramiko
import re

# disable warnings from SSL Check
if not sys.warnoptions:
    import warnings

    warnings.simplefilter("ignore")


def findvxrm():
    vxrmIPs = []
    vxrailappl = {}

    try:

        containerVM = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

        for vm in containerVM.view:
            if re.match("VxRail Manager", vm.name, flags=re.IGNORECASE) and vm.summary.guest.ipAddress is not None:
                vxrmIPs.append(vm.summary.guest.ipAddress)
                lenvxrmIPs = len(vxrmIPs)

                vxrailappl[vm.summary.guest.ipAddress] = vm.summary.runtime.host.name

        containerVM.Destroy()

        if len(vxrmIPs) == 0:
            raise RuntimeError('No VMs VxRail Manager Found in Datacenter: Have they been renamed ?')


        else:
            print(f'### Found a Total of: {lenvxrmIPs} VxRail Manager VMs ###\n')


    except Exception  as err:

        print('Error in findvxrm() :', err)
        sys.exit(1)

    return vxrailappl


# Function to modify the URL for the query API.
# Takes the IP and input and returns the modified URL

def modifyurl(ip):
    url = 'https://' + str(ip) + '/rest/vxm/v1/'
    return str(url)


# function that return the endpoint for the API CALL

def endpoint_url(ip, api):
    endpoint = 'https://{0}/rest/vxm/v1/{1}'.format(str(ip), str(api))

    return endpoint


# Function that takes an argument and calls a set of API based on a list
# below function just needs to execute the API call and pass the parameters

def call_api(url, method):

    args = GetArgs()

    auth = vars(args)

    # common to all requests

    creds = (auth['user'], auth['password'])
    headers = {'Content-type': 'application/json'}

    try:

        # parameters is type dictionary !!!! issue may be here
        response = requests.request(method, url,
                                    verify=False,
                                    headers=headers,
                                    auth=creds,
                                    json=parameters)

        result = response.status_code
        print(f'API Call {url} Submitted and Return Code is: {response.status_code} \n'
              f'API Response is: {jsbeautifier.beautify(response.text)}')

        # below condition needed to deal with POST requests.
        # we get the request_id and process it in order to track it

        if method == 'POST':

            print('Waiting to get the Response from the Request ...\n')

            job_id = response.json()
            # exclude POST requests that fail for x and y reasons like storage full
            if job_id is not None:
                req_id = job_id.get('request_id')

                resp_get_id = requests.request('GET', 'https://' + selection + '/rest/vxm/v1/requests/' + req_id,
                                               verify=False,
                                               auth=creds)

                beauty = jsbeautifier.beautify(resp_get_id.text)

                print('''\t
            ##################################\t
            # The Status of the API CALL is: #\t
            ##################################\t
                ''', beauty)

        return result


    except Exception  as err:
        print('Error in call_api(): ', err, response.text)


# function to deal with all the different APIs for VXRM
# needs to deal with POST and GET APIs ....
# this is to replace the need for the user to manually write the api name
# For POST requested we will also have to sort out the details
# we also need to take in account the vxrail manager version as not all APIs are available


def api_list(ip):
    global method
    global parameters
    call = None
    api = None

    api_choices = {
        "Exit/Quit": "0",
        "System Health": '1',
        "System Info": '2',
        "Support Logs": '3',
        "Cluster Shutdown": '4',
        "LCM Upgrade": '5',
        "Available Nodes": '6',
        "VxRM Internet Mode": '7',
        "VxRM Show Proxy Settings": '8',
        "VxRM Get ESRS Heartbeat": '9'
    }

    try:
        ans = True
        while ans:

            for k, v in api_choices.items():
                print(v, k)

            ans = input('''\nWhat API would you like to call?\nType your Choice: ''')

            if ans == '1':
                res = system_health(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '2':
                res = system_info(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '3':
                res = support_logs(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '4':
                res = cluster_shutdown(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '5':
                res = lcm_upgrade(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '6':
                res = available_nodes(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '7':
                res = internet_mode(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '8':
                res = get_system_proxy(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '9':
                res = get_vxrail_heartbeat(ip)
                call = res[0]
                api = res[1]
                method = res[2]
                parameters = res[3]
                break
            elif ans == '0':
                print('\nExiting Program ...')
                sys.exit(1)
            else:
                print('\n Not Valid Choice Try again')

    except Exception  as err:
        print('Error in api_list(): ', err)

    return call, api, method


def GetArgs():
    """
    Supports the command-line arguments listed below.
    """

    parser = argparse.ArgumentParser(description='Process args for connecting to vCenter')
    parser.add_argument('-v', '--vc', required=True, action='store', help='vCenter')
    parser.add_argument('-u', '--user', required=True, action='store', help='vCenter Administrator')
    parser.add_argument('-p', '--password', required=False, action='store', help='Password')
    args = parser.parse_args()
    return args


# Runs the same API across all the VXRM Identified
# usually for GET methods

def run_same_api():
    vxrails = findvxrm()
    selected_api = api_list(next(iter(
        vxrails)))  # we need just to pass an IP to api_list to construct the selection list for the available API's

    try:

        for vx in vxrails:
            url = endpoint_url(vx, selected_api[1])
            print(f'API Call Running is: {url}')
            call_api(url, selected_api[2])

    except Exception  as err:

        print('Error in run_same_api(): ', err)

    return selected_api


def system_health(ip):
    call = None
    api = 'system-health'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('Error in system_health(): ', err)

    return call, api, method, parameters


def system_info(ip):
    call = None
    api = 'system'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('Error in system_info(): ', err)

    return call, api, method, parameters


def support_logs(ip):
    call = None
    api = 'support/logs'
    method = 'POST'
    parameters = {"types": ["vxm", "vcenter", "esxi", "idrac", "ptagent"]}

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('Error in support_logs(): ', err)

    return call, api, method, parameters


def cluster_shutdown(ip):
    call = None
    api = 'cluster/shutdown'
    method = 'POST'
    param = input('''Select Operation Type:\n1 - Dry Run Only\n2 - Cluster Shutdown\nType your Choice: ''')
    if param == '1':
        parameters = {"dryrun": "true"}
    else:
        parameters = {"dryrun": "false"}

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('Error in cluster_shutdown(): ', err)

    return call, api, method, parameters


def lcm_upgrade(ip):
    call = None
    api = 'lcm/upgrade'
    method = 'POST'
    parameters = None

    try:
        go = input('''Verify that the following requirements are met: \n
        1 - Have user account details for vxrail root user / vCenter administrator

        Type Y to Continue or N to Cancel:''')

        if go == 'Y':
            print('Upgrade via API starting Now ...')
            copy_bundle(ip)
            print('\n')
            bundle_name = '/tmp/' + bundle_filename
            print(bundle_name)
            vxrm_root_pwd = getpass.getpass(prompt='VxRail root Password: ')
            vc_admin_pwd = getpass.getpass(prompt='vCenter Admin Password: ')
            parameters = {"bundle_file_locator": bundle_name,
                          "vxrail": {"vxm_root_user": {"username": "root", "password": vxrm_root_pwd}},
                          "vcenter": {
                              "vc_admin_user": {"username": "administrator@vsphere.local", "password": vc_admin_pwd}}}
            call = endpoint_url(ip, api)

        else:
            print('Cancelling Upgrade ...\n')

    except Exception  as err:
        print('Error in lcm_upgrade(): ', err)

    return call, api, method, parameters


def available_nodes(ip):
    call = None
    api = 'clusters/available-nodes'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('Error in available_nodes(): ', err)

    return call, api, method, parameters


def internet_mode(ip):
    call = None
    api = 'system/internet-mode'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('internet_mode(): ', err)

    return call, api, method, parameters


def get_system_proxy(ip):
    call = None
    api = 'system/proxy'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('system_proxy(): ', err)

    return call, api, method, parameters


def get_vxrail_heartbeat(ip):
    call = None
    api = 'support/heartbeat'
    method = 'GET'
    parameters = None

    try:
        call = endpoint_url(ip, api)

    except Exception  as err:
        print('get_vxrail_heartbeat(): ', err)

    return call, api, method, parameters


def copy_bundle(vxrail_ip):
    vxrm_location = '/tmp'
    global bundle_filename

    try:

        # Define progress callback that prints the current percentage completed for the file
        def progress(filename, size, sent):
            sys.stdout.buffer.write(b"%s\'s progress: %.2f%%   \r" % (filename, float(sent) / float(size) * 100))

        bundle = input('Type the location of the Upgrade Bundle on your local machine')
        bundle_filename = os.path.basename(bundle)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_system_host_keys()
        ssh.connect(vxrail_ip, username='mystic', password='VxRailManager@201602!')

        # SCPCLient takes a paramiko transport as an argument
        scp = SCPClient(ssh.get_transport(), progress=progress)

        # Uploading
        scp.put(bundle, recursive=False, remote_path=vxrm_location)
        stdin, stdout, stderr = ssh.exec_command('chmod 777 ' + vxrm_location + '/' + bundle_filename)


        scp.close()
    except Exception  as err:
        print('copy_bundle(): ', err)

    return None


def main():
    global content
    global si

    args = GetArgs()

    if args.password:
        password = args.password
    else:
        password = getpass.getpass(prompt='Enter password for host %s and user %s: ' % (args.vc, args.user))

    try:

        # connection string

        si = connect.SmartConnectNoSSL(host=args.vc,
                                       user=args.user,
                                       pwd=password)

        content = si.RetrieveServiceContent()
        # we close the vc connection
        atexit.register(connect.Disconnect, si)

        while True:
            global selection
            vx = findvxrm()
            print('Continue ?')
            cont = input('Type Y or N: ')
            if cont == 'Y':
                for vxrm_ip, esxi in vx.items():
                    print(f'VXRM Found with IP: {vxrm_ip} running on ESXi: {esxi} \n')

                selection = input(
                    'Type the IP of VxRM to Connect to or type "all" to run the same API on ALL VxRM : ')
                if selection in vx:

                    print('Checking VxRail Manager: ', selection)

                    api = api_list(selection)

                    if api is not None:

                        call_api(api[0], api[2])

                    else:
                        break
                elif selection == 'all':
                    run_same_api()

            else:
                print('\nExiting Program ...')
                sys.exit(1)

    except Exception  as err:

        print('Error in main(): ', err)


main()

# Things to improve/implement
# MAJOR FEATURES

# todo - Add support for more APIs
# todo - Add to each API a description of what they actually do

# MINOR FEATURES
